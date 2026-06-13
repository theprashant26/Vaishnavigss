"""
Load initial Vaishnavi Gaushala data.

Reads JSON from ../Vaishanvigss/assets/data/*.json plus a small amount of
inline seed data for breeds, FAQs, and a default SiteSettings row.

Idempotent: re-running update_or_creates on slug. Use --reset to wipe first.
"""
import json
import re
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile  # noqa: F401  (kept for future seed expansion)
from catalog.models import Breed, Category, Cow, Product, ProductImage, ProductVariant
from core.models import FAQ, SiteSettings, Testimonial
from services.models import Service
from subscriptions.models import SubscriptionPlan, SubscriptionPlanItem


# ---------------------------------------------------------------------------
# Canonical breed seed (overrides any JSON spellings — per spec).
# ---------------------------------------------------------------------------
BREED_SEED = [
    {
        'slug': 'gir',
        'name': 'Gir',
        'region': 'Gujarat',
        'key_traits': 'A2 milk with high butterfat. Hardy, gentle, the classic Indian dairy breed.',
        'description': (
            'Reddish, often white-patched. The most widely recognised indigenous '
            'Indian dairy breed. Distinctive convex forehead and pendulous ears — '
            'features shaped by climate, not breeding committees.'
        ),
    },
    {
        'slug': 'sahiwal',
        'name': 'Sahiwal',
        'region': 'Punjab / Haryana',
        'key_traits': "India's finest dairy breed. Heat-tolerant, calm-tempered, consistently high-yielding.",
        'description': (
            'Reddish-brown. A Sahiwal cow can produce milk in 40 °C heat that '
            "would shut down a Holstein-Friesian's lactation."
        ),
    },
    {
        'slug': 'tharparkar',
        'name': 'Tharparkar',
        'region': 'Rajasthan · Thar desert',
        'key_traits': "Dual-purpose, drought-resistant, deep-chested. The cow that survives where others can't.",
        'description': (
            'White or grey. Named for the Thar Parkar region. Was nearly lost '
            'during Partition; conservation programmes brought the breed back.'
        ),
    },
    {
        'slug': 'bachaur',
        'name': 'Bachaur',
        'region': 'Bihar · Sitamarhi',
        'key_traits': 'Compact, strong, traditionally a draught + dairy breed. Quiet temperament.',
        'description': (
            'Greyish-white. Named for the Bachaur region near the Nepal border. '
            'Less famous than Gir or Sahiwal but every bit as important to local '
            'farming heritage.'
        ),
    },
    {
        'slug': 'punganur',
        'name': 'Punganur',
        'region': 'Andhra Pradesh · Chittoor',
        'key_traits': (
            'One of the smallest cattle breeds in the world. Dwarf stature, '
            'A2 milk with very high butterfat. Sacred in temple traditions.'
        ),
        'description': (
            'Usually white or fawn. An adult Punganur stands about 70–90 cm at '
            'the shoulder — a 5-year-old child looks her in the eye.'
        ),
    },
]


# ---------------------------------------------------------------------------
# FAQ seed.
# ---------------------------------------------------------------------------
FAQ_SEED = [
    # General
    (FAQ.GENERAL, 'What does "A2" milk mean?', (
        'A2 refers to the beta-casein protein in milk. Indigenous Indian breeds '
        '(Gir, Sahiwal, Tharparkar, Bachaur, Punganur) produce milk with only '
        'the A2 variant, which many people find easier to digest than the A1 '
        'milk from cross-bred Holstein-Friesian cows.'
    ), 10),
    (FAQ.GENERAL, 'Where is the gaushala located?', (
        'Our gaushala is in Delhi NCR. Visits are open every Saturday and '
        'Sunday, 8–11 am and 4–6 pm. Address details and a map are on the '
        'Contact page.'
    ), 20),
    (FAQ.GENERAL, 'How many cows do you care for?', (
        'We currently care for 35+ indigenous cows across five breeds — Gir, '
        'Sahiwal, Tharparkar, Bachaur and Punganur. Each one is named, '
        'tracked, and has a personal profile in the "Meet the Cows" gallery.'
    ), 30),
    # Products
    (FAQ.PRODUCTS, 'What is bilona ghee?', (
        'Bilona is the traditional eight-step ghee-making process: milk → curd '
        '→ hand-churned makhan → slowly simmered ghee. It takes three days '
        'and produces a granular, deep-aromatic ghee — the opposite of the '
        'cream-centrifuged industrial product sold as ghee in most shops.'
    ), 10),
    (FAQ.PRODUCTS, 'Are your products organic?', (
        'Our cows graze on chemical-free fodder and we never use antibiotics '
        'or hormones. Formal organic certification is in progress; until then '
        'we describe our products as "naturally raised, traditionally made".'
    ), 20),
    # Delivery
    (FAQ.DELIVERY, 'Do you deliver outside Delhi NCR?', (
        'Yes — ghee, snacks and hampers ship pan-India via insured courier '
        'in 2–5 business days. Fresh A2 milk and buttermilk are NCR-only, '
        'because they cannot survive longer transit while remaining fresh.'
    ), 10),
    (FAQ.DELIVERY, 'When does the milk arrive?', (
        'Daily NCR milk delivery is a 5–9 am slot. Bottles are glass and '
        'returnable — leave yesterday\'s empty out for collection.'
    ), 20),
    # Subscription
    (FAQ.SUBSCRIPTION, 'Can I pause or skip a subscription?', (
        'Yes, any time, from your profile dashboard. There are no lock-ins '
        'or cancellation fees on any of our subscription tiers.'
    ), 10),
    # Adoption
    (FAQ.ADOPTION, 'How does the Cow Adoption Program work?', (
        'You sponsor one cow for ₹4,999/month. In return you receive monthly '
        'photos, naming rights, a share of her milk and ghee, and full '
        'transparency on her welfare. See the Services page for more.'
    ), 10),
]


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------
TIER_MAP = {
    'daily': SubscriptionPlan.DAILY_ESSENTIALS,
    'pantry': SubscriptionPlan.MONTHLY_PANTRY,
    'boxes': SubscriptionPlan.CURATED_BOXES,
}

CYCLE_MAP = {
    'month': SubscriptionPlan.MONTHLY,
    'quarter': SubscriptionPlan.QUARTERLY,
    'one-time': SubscriptionPlan.ONE_TIME,
    'day': SubscriptionPlan.DAILY,
}

# Phase 7 — what ships in each delivery for a given plan slug.
# Format: plan_slug → [(product_slug, variant_label, qty_per_delivery), ...]
# Variant labels must match catalog/products.json `sizes[].label`.
PLAN_ITEM_SEED = {
    # Tier A — Daily NCR (qty is per-day per-delivery)
    'milk-mini':    [('a2-desi-cow-milk', '1 litre', 1)],
    'milk-family':  [('a2-desi-cow-milk', '2 litres', 1)],
    'milk-chaas':   [('a2-desi-cow-milk', '2 litres', 1),
                     ('fresh-buttermilk', '1 litre', 1)],
    'joint-family': [('a2-desi-cow-milk', '2 litres', 1),
                     ('a2-desi-cow-milk', '1 litre', 1)],
    # Tier B — Monthly pantry (one delivery per period)
    'ghee-petite':    [('a2-bilona-ghee', '250 g', 1)],
    'ghee-classic':   [('a2-bilona-ghee', '500 g', 1)],
    'ghee-grand':     [('a2-bilona-ghee', '1 kg', 1)],
    'ghee-quarterly': [('a2-bilona-ghee', '1 kg', 1)],
    # Tier C — Curated boxes (per-delivery snapshots)
    'tea-time': [
        ('thekua-bihar-sweet', '250 g', 1),
        ('nimki-savoury', '250 g', 1),
        ('mathri-spiced-biscuit', '250 g', 1),
    ],
    'heritage-hamper': [
        ('thekua-bihar-sweet', '500 g', 1),
        ('nimki-savoury', '500 g', 1),
        ('mathri-spiced-biscuit', '500 g', 1),
        ('a2-bilona-ghee', '250 g', 1),
    ],
    'pooja-pack': [
        ('a2-bilona-ghee', '500 g', 1),
        ('thekua-bihar-sweet', '250 g', 1),
        ('nimki-savoury', '250 g', 1),
        ('mathri-spiced-biscuit', '250 g', 1),
    ],
    # 'full-plate' is a bundle of multiple cadences; intentionally not modelled
    # as plan items in Phase 7 — flag for the client.
}

# services.json id → Service.service_type. Entries marked None are skipped
# (they're already represented by SubscriptionPlan).
SERVICE_TYPE_MAP = {
    'adoption': Service.ADOPTION,
    'visit': Service.VISIT,
    'wholesale': Service.WHOLESALE,
    'pooja': Service.HAMPER,
    'milk-subscription': None,
    'ghee-subscription': None,
}

# Phase 7 — `period` in subscriptions.json describes BILLING cadence ("month").
# For NCR daily-milk plans the DELIVERY cadence is daily even though billing is
# monthly. Override the JSON-derived delivery_frequency for these plans.
DELIVERY_FREQ_OVERRIDE = {
    'milk-mini':    SubscriptionPlan.DAILY,
    'milk-family':  SubscriptionPlan.DAILY,
    'milk-chaas':   SubscriptionPlan.DAILY,
    'joint-family': SubscriptionPlan.DAILY,
    'full-plate':   SubscriptionPlan.DAILY,
}


def _parse_age_years(value):
    """'9 years' → 9, '6 months' → 0, garbage → None."""
    if not value:
        return None
    m = re.match(r'\s*(\d+)', str(value))
    if not m:
        return None
    n = int(m.group(1))
    if 'year' not in str(value).lower():
        return None
    return n


def _format_nutrition(raw):
    """Take {'energy': '67 kcal', 'protein': '3.4 g', ...} → flat text block."""
    if not isinstance(raw, dict):
        return ''
    label_map = {
        'energy': 'Energy', 'protein': 'Protein', 'fat': 'Fat',
        'saturatedFat': 'Saturated fat', 'carbs': 'Carbohydrates',
        'calcium': 'Calcium', 'vitaminA': 'Vitamin A', 'cla': 'CLA',
    }
    parts = []
    for key, value in raw.items():
        label = label_map.get(key, key.title())
        parts.append(f'{label}: {value}')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Command.
# ---------------------------------------------------------------------------
class Command(BaseCommand):
    help = 'Seed the database with Vaishnavi initial data (idempotent).'

    DATA_DIR = Path(__file__).resolve().parents[3].parent / 'Vaishanvigss' / 'assets' / 'data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Delete all seeded data first (asks for confirmation unless --no-input).',
        )
        parser.add_argument(
            '--no-input', action='store_true',
            help='Skip confirmation prompts.',
        )

    def handle(self, *args, **opts):
        if opts['reset']:
            if not opts['no_input']:
                answer = input(
                    'This will DELETE all Categories, Breeds, Cows, Products, '
                    'Variants, Images, Testimonials, FAQs, Services, '
                    'SubscriptionPlans, and the SiteSettings row. '
                    'Type "yes" to confirm: '
                )
                if answer.strip().lower() != 'yes':
                    self.stdout.write(self.style.WARNING('Aborted.'))
                    return
            self._reset()

        # Count of images we tried to copy but couldn't find on disk.
        self.missing_images = 0

        with transaction.atomic():
            n_breeds = self._load_breeds()
            n_categories = self._load_categories()
            n_cows = self._load_cows()
            n_products, n_variants, n_gallery = self._load_products()
            n_testimonials = self._load_testimonials()
            n_subscriptions = self._load_subscriptions()
            n_plan_items, n_plan_items_missing = self._load_plan_items()
            n_services, n_services_skipped = self._load_services()
            n_faqs = self._load_faqs()
            self._load_site_settings()

        self.stdout.write(self.style.SUCCESS('\nSeed complete:'))
        self.stdout.write(f'  Breeds:           {n_breeds}')
        self.stdout.write(f'  Categories:       {n_categories}')
        self.stdout.write(f'  Cows:             {n_cows}')
        self.stdout.write(f'  Products:         {n_products}')
        self.stdout.write(f'    Variants:       {n_variants}')
        self.stdout.write(f'    Gallery imgs:   {n_gallery}')
        self.stdout.write(f'  Testimonials:     {n_testimonials}')
        self.stdout.write(f'  Subscriptions:    {n_subscriptions}')
        self.stdout.write(f'    Plan items:     {n_plan_items} (skipped {n_plan_items_missing} — missing variants)')
        self.stdout.write(f'  Services:         {n_services} (skipped {n_services_skipped} — already in subscriptions)')
        self.stdout.write(f'  FAQs:             {n_faqs}')
        self.stdout.write(f'  SiteSettings:     1 (singleton)')
        if self.missing_images:
            self.stdout.write(
                f'  Skipped {self.missing_images} missing image files '
                f'(placeholders not yet shot — fill via admin).'
            )

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    def _reset(self):
        # Order matters because of PROTECT FKs.
        ProductVariant.objects.all().delete()
        ProductImage.objects.all().delete()
        Product.objects.all().delete()
        Cow.objects.all().delete()
        Breed.objects.all().delete()
        Category.objects.all().delete()
        Testimonial.objects.all().delete()
        FAQ.objects.all().delete()
        SubscriptionPlanItem.objects.all().delete()
        SubscriptionPlan.objects.all().delete()
        Service.objects.all().delete()
        SiteSettings.objects.all().delete()
        self.stdout.write(self.style.WARNING('Reset done.\n'))

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------
    def _read_json(self, filename):
        path = self.DATA_DIR / filename
        if not path.exists():
            self.stdout.write(self.style.WARNING(f'Missing {path} — skipping.'))
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _attach_image(self, instance, field_name, web_path):
        """Try to find a file under ../Vaishanvigss/assets/... matching web_path.

        web_path looks like '/assets/img/products/ghee-bilona.jpg'. Most of
        these files don't yet exist on disk — we silently skip them and bump
        the missing-image counter.
        """
        if not web_path:
            return False
        relative = web_path.lstrip('/').removeprefix('assets/')
        candidate = self.DATA_DIR.parent / relative
        if not candidate.exists() or not candidate.is_file():
            self.missing_images += 1
            return False
        with open(candidate, 'rb') as fh:
            getattr(instance, field_name).save(
                candidate.name, File(fh), save=False
            )
        return True

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------
    def _load_breeds(self):
        for order, row in enumerate(BREED_SEED):
            Breed.objects.update_or_create(
                slug=row['slug'],
                defaults={
                    'name': row['name'],
                    'region': row['region'],
                    'description': row['description'],
                    'key_traits': row['key_traits'],
                    'display_order': order,
                },
            )
        return Breed.objects.count()

    def _load_categories(self):
        data = self._read_json('categories.json') or []
        for order, row in enumerate(data):
            obj, _ = Category.objects.update_or_create(
                slug=row['id'],
                defaults={
                    'name': row['name'],
                    'description': row.get('description', ''),
                    'display_order': order,
                    'is_active': True,
                },
            )
            if self._attach_image(obj, 'image', row.get('image')):
                obj.save()
        return Category.objects.count()

    def _load_cows(self):
        data = self._read_json('cows.json') or []
        for order, row in enumerate(data):
            try:
                breed = Breed.objects.get(slug=row['breedSlug'])
            except Breed.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'  Cow {row["name"]}: breed {row["breedSlug"]} not found, skipping.'
                ))
                continue
            obj, _ = Cow.objects.update_or_create(
                name=row['name'],
                defaults={
                    'breed': breed,
                    'age_years': _parse_age_years(row.get('age')),
                    'bio': row.get('story', ''),
                    'is_featured': bool(row.get('isHero', False)),
                    'display_order': order,
                },
            )
            if self._attach_image(obj, 'photo', row.get('image')):
                obj.save()
        return Cow.objects.count()

    def _load_products(self):
        data = self._read_json('products.json') or []
        n_variants = 0
        n_gallery = 0
        for order, row in enumerate(data):
            try:
                category = Category.objects.get(slug=row['category'])
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'  Product {row["slug"]}: category {row["category"]} not found, skipping.'
                ))
                continue

            nutrition = row.get('nutritionPer100ml') or row.get('nutritionPer100g') or {}
            product, _ = Product.objects.update_or_create(
                slug=row['slug'],
                defaults={
                    'name': row['name'],
                    'category': category,
                    'short_description': row.get('shortDescription', '')[:300],
                    'description': row.get('longDescription', ''),
                    'how_its_made': row.get('howItsMade', ''),
                    'nutrition_info': _format_nutrition(nutrition),
                    'is_featured': bool(row.get('isBestseller', False)),
                    'is_active': bool(row.get('inStock', True)),
                    'display_order': order,
                },
            )
            if self._attach_image(product, 'image', row.get('image')):
                product.save()

            # Variants (sizes). update_or_create on (product, label).
            for v_order, size in enumerate(row.get('sizes', [])):
                ProductVariant.objects.update_or_create(
                    product=product,
                    label=size['label'],
                    defaults={
                        'price': Decimal(str(size['price'])),
                        'stock_quantity': 100,  # arbitrary positive default
                        'is_active': True,
                        'display_order': v_order,
                    },
                )
                n_variants += 1

            # Gallery images. Wipe and reinsert in JSON order for idempotency.
            ProductImage.objects.filter(product=product).delete()
            for g_order, gallery_path in enumerate(row.get('gallery', [])):
                gi = ProductImage(
                    product=product,
                    alt_text=row.get('imageAlt', '')[:200],
                    display_order=g_order,
                )
                if self._attach_image(gi, 'image', gallery_path):
                    gi.save()
                    n_gallery += 1
                # If image file is missing, don't create a row at all
                # (ImageField is required on ProductImage).
        return Product.objects.count(), n_variants, n_gallery

    def _load_testimonials(self):
        data = self._read_json('testimonials.json') or []
        for order, row in enumerate(data):
            obj, _ = Testimonial.objects.update_or_create(
                customer_name=row['name'],
                defaults={
                    'location': row.get('location', ''),
                    'rating': row.get('rating', 5),
                    'content': row.get('quote', ''),
                    'is_featured': True,
                    'display_order': order,
                },
            )
            if self._attach_image(obj, 'photo', row.get('avatar')):
                obj.save()
        return Testimonial.objects.count()

    def _load_subscriptions(self):
        data = self._read_json('subscriptions.json') or {}
        order_counter = 0
        for tier_block in data.get('tiers', []):
            tier_key = TIER_MAP.get(tier_block['id'])
            if tier_key is None:
                self.stdout.write(self.style.WARNING(
                    f'  Unknown subscription tier {tier_block["id"]}, skipping.'
                ))
                continue
            scope = (
                SubscriptionPlan.NCR_ONLY
                if tier_block['id'] == 'daily'
                else SubscriptionPlan.PAN_INDIA
            )
            for plan_order, plan in enumerate(tier_block.get('plans', [])):
                json_cycle = CYCLE_MAP.get(plan.get('period', 'month'), SubscriptionPlan.MONTHLY)
                # Phase 7: billing_period_days comes from JSON cycle; delivery_frequency
                # may be overridden per-plan (NCR daily milk is billed monthly).
                billing_period_days = {
                    SubscriptionPlan.DAILY: 30,
                    SubscriptionPlan.MONTHLY: 30,
                    SubscriptionPlan.QUARTERLY: 90,
                    SubscriptionPlan.ONE_TIME: 0,
                }.get(json_cycle, 30)
                cycle = DELIVERY_FREQ_OVERRIDE.get(plan['id'], json_cycle)
                items = plan.get('items', [])
                whats_included = '\n'.join(f'• {item}' for item in items)
                SubscriptionPlan.objects.update_or_create(
                    slug=plan['id'],
                    defaults={
                        'tier': tier_key,
                        'name': plan['name'],
                        'description': plan.get('contents', ''),
                        'whats_included': whats_included,
                        'price': Decimal(str(plan['price'])),
                        'delivery_frequency': cycle,
                        'delivery_scope': scope,
                        'billing_period_days': billing_period_days,
                        'is_active': True,
                        'is_featured': plan.get('badge') == 'Most Popular',
                        'display_order': plan_order,
                    },
                )
                order_counter += 1
        return SubscriptionPlan.objects.count()

    def _load_plan_items(self):
        """Idempotent. Populates SubscriptionPlanItem for known plans.

        Skips (and logs) any plan or variant that can't be resolved — Phase 2
        catalog data is a prerequisite.
        """
        created = 0
        missing = 0
        for plan_slug, items in PLAN_ITEM_SEED.items():
            try:
                plan = SubscriptionPlan.objects.get(slug=plan_slug)
            except SubscriptionPlan.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'  Plan items: plan "{plan_slug}" not found, skipping.'
                ))
                continue
            for display_order, (product_slug, label, qty) in enumerate(items):
                try:
                    variant = ProductVariant.objects.get(
                        product__slug=product_slug, label=label,
                    )
                except ProductVariant.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f'  Plan items: variant {product_slug}/{label} '
                        f'not found for plan "{plan_slug}", skipping.'
                    ))
                    missing += 1
                    continue
                SubscriptionPlanItem.objects.update_or_create(
                    plan=plan,
                    variant=variant,
                    defaults={
                        'quantity_per_delivery': Decimal(str(qty)),
                        'display_order': display_order,
                    },
                )
                created += 1
        return created, missing

    def _load_services(self):
        data = self._read_json('services.json') or []
        skipped = 0
        for order, row in enumerate(data):
            service_type = SERVICE_TYPE_MAP.get(row['id'], Service.OTHER)
            if service_type is None:
                # Already represented as a SubscriptionPlan — skip.
                skipped += 1
                continue
            price_display = ''
            if service_type == Service.ADOPTION:
                price_display = '₹4,999 / month (or ₹49,999 / year)'
            elif service_type == Service.VISIT:
                price_display = 'Free · Saturdays & Sundays · 8–11 am, 4–6 pm'
            elif service_type == Service.WHOLESALE:
                price_display = 'Custom quote · minimum order applies'
            elif service_type == Service.HAMPER:
                price_display = 'From ₹2,500 · custom-built per festival'

            Service.objects.update_or_create(
                slug=row['id'],
                defaults={
                    'name': row['name'],
                    'service_type': service_type,
                    'short_description': row.get('tagline', '')[:300],
                    'description': row.get('description', ''),
                    'price_display': price_display,
                    'is_active': True,
                    'display_order': order,
                },
            )
        return Service.objects.count(), skipped

    def _load_faqs(self):
        for order, (cat, q, a, ord_within) in enumerate(FAQ_SEED):
            FAQ.objects.update_or_create(
                question=q,
                defaults={
                    'answer': a,
                    'category': cat,
                    'display_order': ord_within,
                    'is_active': True,
                },
            )
        return FAQ.objects.count()

    def _load_site_settings(self):
        site = SiteSettings.load()
        # Only fill blanks — never overwrite real client data once entered.
        defaults = {
            'business_name': 'Vaishnavi Gau Seva Gausansthan',
            'tagline': 'Pure. Sacred. From our gaushala to your home.',
            # Real gaushala address (Patna, Bihar). Update via admin if you move.
            'address_line_1': 'Vill Jaiver, P.S. Gaurichak, P.O. Nadh Ghat',
            'address_line_2': 'Landmark: Gaurichak Power Grid',
            'city': 'Patna',
            'state': 'Bihar',
            'pincode': '800007',
            'phone_primary': '+91 78700 85221',
            'phone_whatsapp': '+91 78700 85221',
            'email_primary': 'seva@vaishnavigss.com',
            'business_hours': 'Mon–Sun · 6 AM – 8 PM',
            'cow_count': 35,
        }
        changed = False
        for field, value in defaults.items():
            if not getattr(site, field):
                setattr(site, field, value)
                changed = True
        if changed:
            site.save()

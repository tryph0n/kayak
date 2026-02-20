# Installer: pip install scrapy-playwright playwright
# Puis: playwright install chromium

import scrapy
from scrapy_playwright.page import PageMethod
import json


class BookingPlaywrightSpider(scrapy.Spider):
    name = 'booking_playwright'
    
    # Liste des villes à scraper (passée depuis run_scraper.py)
    cities = []
    # Nombre d'hôtels à scraper par ville (passé depuis run_scraper.py)
    max_hotels = 10
    
    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
        },
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
    }
    
    def start_requests(self):
        """Génère les requêtes pour chaque ville"""
        for city in self.cities:
            url = f'https://www.booking.com/searchresults.html?ss={city}&dest_type=city&order=review_score_and_price'
            
            yield scrapy.Request(
                url,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                        PageMethod('wait_for_timeout', 3000),
                        PageMethod('wait_for_selector', '[data-testid="property-card"]', timeout=30000),
                    ],
                    'city_name': city,
                },
            )
    
    def parse(self, response):
        """Parse la page de résultats et extrait les liens des hôtels"""
        city_name = response.meta.get('city_name')
        hotels = response.css('[data-testid="property-card"]')
        self.logger.info(f"Trouvé {len(hotels)} hôtels pour {city_name}")
        
        # Limiter au nombre d'hôtels demandé
        for hotel in hotels[:self.max_hotels]:
            hotel_link = hotel.css('a[data-testid="title-link"]::attr(href)').get()
            if hotel_link:
                yield scrapy.Request(
                    response.urljoin(hotel_link),
                    callback=self.parse_hotel,
                    meta={
                        'playwright': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_load_state', 'networkidle'),
                            PageMethod('wait_for_timeout', 2000),
                        ],
                        'city_name': city_name,
                    },
                )

    def parse_hotel(self, response):
        """Parse la page de l'hôtel et extrait les informations du JSON-LD"""
        city_name = response.meta.get('city_name')

        # Chercher le JSON-LD dans la page
        json_ld_script = response.xpath('//script[@type="application/ld+json"]/text()').get()

        hotel_name = None
        address = None
        score = None
        description = None

        if json_ld_script:
            try:
                # Parse the JSON-LD script
                data = json.loads(json_ld_script)

                # Extract hotel name
                hotel_name = data.get('name')

                # Address can be in 'address' dict or directly as a string
                address_data = data.get('address', {})
                if isinstance(address_data, dict):
                    address = address_data.get('streetAddress')
                elif isinstance(address_data, str):
                    address = address_data

                # Score is in aggregateRating
                rating_data = data.get('aggregateRating', {})
                if isinstance(rating_data, dict):
                    score = rating_data.get('ratingValue')

                # Extract description
                description = data.get('description')

            except json.JSONDecodeError as e:
                self.logger.error(f"JSON-LD parsing error: {e}")

        # Fallback to CSS selectors if JSON-LD did not provide the name
        if not hotel_name:
            hotel_name = response.css('h2.pp-header__title::text').get()
            if not hotel_name:
                hotel_name = response.css('[data-testid="title"]::text').get()

        # Fallback to CSS selectors if JSON-LD did not provide the address
        if not address:
            address = response.css('span.hp_address_subtitle::text').get()
            if not address:
                address = response.css('[data-node_tt_id="location_score_tooltip"]::text').get()

        # Fallback to CSS selectors if JSON-LD did not provide the score
        if not score:
            score_text = response.css('.b5cd09854e.d10a6220b4::text').get()
            if score_text:
                score = score_text.strip()

        # Fallback to CSS selectors if JSON-LD did not provide the description
        if not description:
            description = response.css('[data-testid="property-description"] ::text').getall()
            if description:
                description = ' '.join(d.strip() for d in description if d.strip())

        yield {
            'city_name': city_name,
            'hotel_name': hotel_name,
            'url': response.url,
            'score': str(score) if score else None,
            'address': address,
            'description': description,
        }
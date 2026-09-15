"""Hand-authored inputs for build_datapack.py: district facts, name pools, cluster factors and feedback records.

All of it is SAMPLE content for an offline prototype (flagged synthetic_sample in the generated _meta.json).
District population/area are rounded Census-2011-scale figures; block names are real blocks of each district.
"""

# ---------------------------------------------------------------- districts
_GENERIC_VILLAGE_SUPPLIERS = {"fabric_wholesaler": 0.05, "yarn_trader": 0.03, "hardware": 0.12, "cattle_feed": 0.12, "agri_input": 0.12}
_GENERIC_HQ = ["fabric_wholesaler", "yarn_trader", "hardware", "hardware", "cattle_feed", "cattle_feed", "agri_input", "agri_input"]

DISTRICTS = [
    {"id": "bhadohi", "en": "Bhadohi", "hi": "भदोही", "hq_en": "Gyanpur", "hq_hi": "ज्ञानपुर", "lat": 25.39, "lon": 82.57,
     "population": 1578213, "area": 1015, "pool": "north", "spread_km": 18, "lgd_base": 184500,
     "extra_aliases": ["sant ravidas nagar bhadohi"],
     "rrb": ("Baroda UP Bank", "बड़ौदा यूपी बैंक"),
     "hq_suppliers": ["fabric_wholesaler", "fabric_wholesaler", "yarn_trader", "yarn_trader", "yarn_trader", "hardware", "cattle_feed", "agri_input"],
     "village_suppliers": {"yarn_trader": 0.25, "fabric_wholesaler": 0.15, "hardware": 0.1, "cattle_feed": 0.08, "agri_input": 0.08}},
    {"id": "varanasi", "en": "Varanasi", "hi": "वाराणसी", "hq_en": "Varanasi", "hq_hi": "वाराणसी", "lat": 25.32, "lon": 82.97,
     "population": 3676841, "area": 1535, "pool": "north", "spread_km": 20, "lgd_base": 208100,
     "rrb": ("Baroda UP Bank", "बड़ौदा यूपी बैंक"), "hq_suppliers": _GENERIC_HQ + ["yarn_trader", "fabric_wholesaler"],
     "village_suppliers": {**_GENERIC_VILLAGE_SUPPLIERS, "yarn_trader": 0.15, "fabric_wholesaler": 0.12}},
    {"id": "mirzapur", "en": "Mirzapur", "hi": "मिर्ज़ापुर", "hq_en": "Mirzapur", "hq_hi": "मिर्ज़ापुर", "lat": 25.15, "lon": 82.57,
     "population": 2496970, "area": 4521, "pool": "north", "spread_km": 30, "lgd_base": 187300,
     "rrb": ("Baroda UP Bank", "बड़ौदा यूपी बैंक"), "hq_suppliers": _GENERIC_HQ + ["yarn_trader"],
     "village_suppliers": {**_GENERIC_VILLAGE_SUPPLIERS, "yarn_trader": 0.08}},
    {"id": "jaunpur", "en": "Jaunpur", "hi": "जौनपुर", "hq_en": "Jaunpur", "hq_hi": "जौनपुर", "lat": 25.75, "lon": 82.69,
     "population": 4494204, "area": 4038, "pool": "north", "spread_km": 28, "lgd_base": 186200,
     "rrb": ("Baroda UP Bank", "बड़ौदा यूपी बैंक"), "hq_suppliers": _GENERIC_HQ, "village_suppliers": _GENERIC_VILLAGE_SUPPLIERS},
    {"id": "prayagraj", "en": "Prayagraj", "hi": "प्रयागराज", "hq_en": "Prayagraj", "hq_hi": "प्रयागराज", "lat": 25.44, "lon": 81.85,
     "population": 5954391, "area": 5482, "pool": "north", "spread_km": 32, "lgd_base": 181400,
     "rrb": ("Aryavart Bank", "आर्यावर्त बैंक"), "hq_suppliers": _GENERIC_HQ, "village_suppliers": _GENERIC_VILLAGE_SUPPLIERS},
    {"id": "gaya", "en": "Gaya", "hi": "गया", "hq_en": "Gaya", "hq_hi": "गया", "lat": 24.8, "lon": 85.01,
     "population": 4391418, "area": 4976, "pool": "north", "spread_km": 30, "lgd_base": 243100,
     "rrb": ("Dakshin Bihar Gramin Bank", "दक्षिण बिहार ग्रामीण बैंक"), "hq_suppliers": _GENERIC_HQ + ["yarn_trader"],
     "village_suppliers": {**_GENERIC_VILLAGE_SUPPLIERS, "yarn_trader": 0.1}},
    {"id": "muzaffarpur", "en": "Muzaffarpur", "hi": "मुज़फ़्फ़रपुर", "hq_en": "Muzaffarpur", "hq_hi": "मुज़फ़्फ़रपुर", "lat": 26.12, "lon": 85.39,
     "population": 4801062, "area": 3172, "pool": "north", "spread_km": 26, "lgd_base": 236500,
     "rrb": ("Uttar Bihar Gramin Bank", "उत्तर बिहार ग्रामीण बैंक"), "hq_suppliers": _GENERIC_HQ + ["cattle_feed"],
     "village_suppliers": {**_GENERIC_VILLAGE_SUPPLIERS, "cattle_feed": 0.15}},
    {"id": "nashik", "en": "Nashik", "hi": "नासिक", "hq_en": "Nashik", "hq_hi": "नासिक", "lat": 19.99, "lon": 73.79,
     "population": 6107187, "area": 15530, "pool": "maharashtra", "spread_km": 45, "lgd_base": 551200,
     "rrb": ("Maharashtra Gramin Bank", "महाराष्ट्र ग्रामीण बैंक"), "hq_suppliers": _GENERIC_HQ + ["agri_input", "agri_input"],
     "village_suppliers": {**_GENERIC_VILLAGE_SUPPLIERS, "agri_input": 0.25, "yarn_trader": 0.01}},
    {"id": "dharwad", "en": "Dharwad", "hi": "धारवाड़", "hq_en": "Dharwad", "hq_hi": "धारवाड़", "lat": 15.46, "lon": 75.01,
     "population": 1847023, "area": 4260, "pool": "karnataka", "spread_km": 28, "lgd_base": 603400,
     "extra_aliases": ["धारवाड", "hubli dharwad"],
     "rrb": ("Karnataka Gramin Bank", "कर्नाटक ग्रामीण बैंक"), "hq_suppliers": _GENERIC_HQ,
     "village_suppliers": {**_GENERIC_VILLAGE_SUPPLIERS, "cattle_feed": 0.15}},
]

# (en, hi[, center_lat, center_lon]) — real development blocks
BLOCKS = {
    "bhadohi": [("Gyanpur", "ज्ञानपुर", 25.30, 82.47), ("Aurai", "औराई"), ("Bhadohi", "भदोही"), ("Deegh", "डीघ"),
                ("Suriyawan", "सुरियावां"), ("Abholi", "अभोली")],
    "varanasi": [("Araziline", "आराजीलाइन"), ("Baragaon", "बड़ागांव"), ("Chiraigaon", "चिरईगांव"), ("Cholapur", "चोलापुर"),
                 ("Harahua", "हरहुआ"), ("Kashi Vidyapeeth", "काशी विद्यापीठ"), ("Pindra", "पिंडरा"), ("Sevapuri", "सेवापुरी")],
    "mirzapur": [("Chhanbey", "छानबे"), ("Kon", "कोन"), ("Majhawan", "मझवां"), ("Pahari", "पहाड़ी"), ("Lalganj", "लालगंज"),
                 ("Halia", "हलिया"), ("Rajgarh", "राजगढ़"), ("Jamalpur", "जमालपुर"), ("Narayanpur", "नारायणपुर"), ("Sikhar", "सीखड़")],
    "jaunpur": [("Shahganj", "शाहगंज"), ("Badlapur", "बदलापुर"), ("Baksha", "बक्शा"), ("Dharmapur", "धर्मापुर"),
                ("Karanjakala", "करंजाकला"), ("Kerakat", "केराकत"), ("Mariahu", "मड़ियाहूं"), ("Muftiganj", "मुफ्तीगंज"),
                ("Sirkoni", "सिरकोनी"), ("Sujanganj", "सुजानगंज")],
    "prayagraj": [("Phulpur", "फूलपुर"), ("Handia", "हंडिया"), ("Soraon", "सोरांव"), ("Karchhana", "करछना"), ("Meja", "मेजा"),
                  ("Koraon", "कोरांव"), ("Shankargarh", "शंकरगढ़"), ("Jasra", "जसरा"), ("Bahadurpur", "बहादुरपुर")],
    "gaya": [("Tekari", "टेकारी"), ("Manpur", "मानपुर"), ("Sherghati", "शेरघाटी"), ("Wazirganj", "वजीरगंज"),
             ("Belaganj", "बेलागंज"), ("Imamganj", "इमामगंज"), ("Dobhi", "डोभी"), ("Bodh Gaya", "बोधगया")],
    "muzaffarpur": [("Kanti", "कांटी"), ("Motipur", "मोतीपुर"), ("Sakra", "सकरा"), ("Mushahari", "मुसहरी"),
                    ("Kurhani", "कुढ़नी"), ("Bochaha", "बोचहां"), ("Minapur", "मीनापुर"), ("Paroo", "पारू")],
    "nashik": [("Niphad", "निफाड"), ("Sinnar", "सिन्नर"), ("Dindori", "दिंडोरी"), ("Igatpuri", "इगतपुरी"),
               ("Chandwad", "चांदवड"), ("Yeola", "येवला"), ("Malegaon", "मालेगाव")],
    "dharwad": [("Hubli", "हुबली"), ("Kalghatgi", "कलघटगी"), ("Kundgol", "कुंदगोल"), ("Navalgund", "नवलगुंद"), ("Alnavar", "अलनावर")],
}

# Repeated village name on purpose (disambiguation). Bhadohi row: LGD 184512 at 25.279, 82.458.
FIXED_VILLAGES = [
    {"lgd": "184512", "en": "Gopiganj", "hi": "गोपीगंज", "block_en": "Gyanpur", "block_hi": "ज्ञानपुर", "district": "bhadohi",
     "lat": 25.279, "lon": 82.458, "population": 24580},
    {"lgd": "186233", "en": "Gopiganj", "hi": "गोपीगंज", "block_en": "Shahganj", "block_hi": "शाहगंज", "district": "jaunpur",
     "lat": 26.021, "lon": 82.662, "population": 2140},
    {"lgd": "243177", "en": "Gopiganj", "hi": "गोपीगंज", "block_en": "Tekari", "block_hi": "टेकारी", "district": "gaya",
     "lat": 24.931, "lon": 84.829, "population": 3050},
]

NAME_POOLS = {
    "north": {
        "prefixes": [("Ram", "राम"), ("Shiv", "शिव"), ("Hari", "हरि"), ("Sultan", "सुल्तान"), ("Chand", "चंद"), ("Madho", "माधो"),
                     ("Bhim", "भीम"), ("Kishan", "किशन"), ("Sher", "शेर"), ("Dev", "देव"), ("Bhagwan", "भगवान"),
                     ("Kamal", "कमल"), ("Ratan", "रतन"), ("Mohan", "मोहन"), ("Sita", "सीता"), ("Durga", "दुर्गा"),
                     ("Gauri", "गौरी"), ("Jagdish", "जगदीश"), ("Rasul", "रसूल"), ("Karim", "करीम"), ("Bishun", "बिशुन"),
                     ("Hanuman", "हनुमान"), ("Mahesh", "महेश"), ("Bhawani", "भवानी"), ("Anand", "आनंद"), ("Bahadur", "बहादुर"),
                     ("Nawab", "नवाब"), ("Sarai", "सराय"), ("Khajuri", "खजुरी"), ("Baraula", "बरौला")],
        "suffixes": [("pur", "पुर"), ("ganj", "गंज"), ("nagar", "नगर"), ("patti", "पट्टी"), ("garh", "गढ़"), ("pura", "पुरा"),
                     ("dih", "डीह"), ("tola", "टोला")],
    },
    "maharashtra": {
        "prefixes": [("Pimpal", "पिंपळ"), ("Wad", "वड"), ("Shir", "शिर"), ("Deo", "देव"), ("Kas", "कस"), ("Nan", "नान"),
                     ("Mohad", "मोहाड"), ("Wan", "वण"), ("Bor", "बोर"), ("Dhon", "धोन"), ("Chinch", "चिंच"), ("Umbar", "उंबर"),
                     ("Ambe", "आंबे"), ("Nimb", "निंब"), ("Kothur", "कोठुर"), ("Palas", "पळस")],
        "suffixes": [("gaon", "गाव"), ("wadi", "वाडी"), ("khed", "खेड"), ("ner", "नेर"), ("pada", "पाडा")],
    },
    "karnataka": {
        "prefixes": [("Hebba", "हेब्ब"), ("Kalla", "कल्ल"), ("Hosa", "होस"), ("Bela", "बेल"), ("Gara", "गर"), ("Mada", "मद"),
                     ("Hire", "हिरे"), ("Chikka", "चिक्क"), ("Ninga", "निंग"), ("Uppin", "उप्पिन"), ("Kote", "कोटे"),
                     ("Timma", "तिम्म"), ("Ammin", "अम्मिन"), ("Kyara", "क्यार"), ("Sula", "सुल")],
        "suffixes": [("halli", "हल्ली"), ("koppa", "कोप्प"), ("gere", "गेरे"), ("bhavi", "भावी"), ("hal", "हाल")],
    },
}

SURNAMES = {
    "north": [("Ansari", "अंसारी"), ("Maurya", "मौर्य"), ("Yadav", "यादव"), ("Patel", "पटेल"), ("Gupta", "गुप्ता"),
              ("Sharma", "शर्मा"), ("Verma", "वर्मा"), ("Khan", "खान"), ("Singh", "सिंह"), ("Prajapati", "प्रजापति"),
              ("Pal", "पाल"), ("Bind", "बिंद"), ("Kushwaha", "कुशवाहा"), ("Jaiswal", "जायसवाल"), ("Saroj", "सरोज")],
    "maharashtra": [("Patil", "पाटील"), ("Jadhav", "जाधव"), ("Pawar", "पवार"), ("Shinde", "शिंदे"), ("More", "मोरे"),
                    ("Gaikwad", "गायकवाड"), ("Deshmukh", "देशमुख"), ("Kale", "काळे")],
    "karnataka": [("Patil", "पाटील"), ("Hiremath", "हिरेमठ"), ("Kulkarni", "कुलकर्णी"), ("Gowda", "गौडा"), ("Naik", "नायक"),
                  ("Hosamani", "होसमनी"), ("Desai", "देसाई")],
}

DAYS = [("Mon", "सोमवार"), ("Tue", "मंगलवार"), ("Wed", "बुधवार"), ("Thu", "गुरुवार"), ("Fri", "शुक्रवार"), ("Sat", "शनिवार"), ("Sun", "रविवार")]

# supplier tags never reuse a catalog osm_tag, so input suppliers are not counted as competitors
SUPPLIERS = {
    "fabric_wholesaler": ("Fabric Wholesale", "कपड़ा थोक", [("shop", "wholesale"), ("wholesale", "fabric"), ("supply", "fabric")]),
    "yarn_trader": ("Yarn Traders", "धागा व्यापारी", [("shop", "wholesale"), ("wholesale", "yarn"), ("supply", "yarn")]),
    "cattle_feed": ("Cattle Feed Depot", "पशु आहार डिपो", [("shop", "wholesale"), ("wholesale", "animal_feed"), ("supply", "cattle_feed")]),
    "agri_input": ("Agri Inputs Wholesale", "कृषि सामग्री थोक", [("shop", "wholesale"), ("wholesale", "agri_inputs"), ("supply", "agri_input")]),
    "hardware": ("Hardware", "हार्डवेयर", [("shop", "hardware"), ("supply", "hardware")]),
}

TAG_LABELS = {
    "shop=dairy": ("Dairy", "डेयरी"), "craft=dairy": ("Milk Centre", "दुग्ध केंद्र"),
    "shop=butcher": ("Meat Shop", "मीट शॉप"), "shop=poultry": ("Poultry", "पोल्ट्री"),
    "shop=seafood": ("Fish Centre", "मछली केंद्र"), "shop=honey": ("Honey Store", "शहद भंडार"),
    "craft=oil_mill": ("Oil Mill", "तेल मिल"), "man_made=works": ("Expeller Works", "एक्सपेलर वर्क्स"),
    "craft=miller": ("Atta Chakki", "आटा चक्की"), "man_made=watermill": ("Grain Mill", "अनाज चक्की"),
    "shop=deli": ("Achar Papad", "अचार पापड़"), "craft=confectionery": ("Namkeen", "नमकीन"),
    "shop=convenience": ("Kirana", "किराना"), "shop=general": ("General Store", "जनरल स्टोर"), "shop=supermarket": ("Mart", "मार्ट"),
    "shop=agrarian": ("Beej Bhandar", "बीज भंडार"), "shop=garden_centre": ("Krishi Kendra", "कृषि केंद्र"),
    "shop=tailor": ("Tailors", "टेलर्स"), "craft=tailor": ("Silai Centre", "सिलाई केंद्र"),
    "craft=weaver": ("Handloom", "हथकरघा"), "shop=fabric": ("Cloth House", "वस्त्र भंडार"),
    "craft=carpet_layer": ("Carpet Unit", "कालीन इकाई"), "shop=carpet": ("Carpet Emporium", "कालीन एम्पोरियम"),
    "shop=mobile_phone": ("Mobile Shop", "मोबाइल शॉप"), "craft=electronics_repair": ("Mobile Repair", "मोबाइल रिपेयर"),
    "shop=beauty": ("Beauty Parlour", "ब्यूटी पार्लर"), "shop=hairdresser": ("Salon", "सैलून"),
    "amenity=cafe": ("Tea Stall", "चाय स्टॉल"), "amenity=fast_food": ("Snacks Corner", "नाश्ता कॉर्नर"),
}

# District craft-cluster factors on the catalog benchmark density (1.0 = benchmark)
FACTORS = {
    "bhadohi": {"carpet_weaving": 6.0, "handloom_weaving": 4.0, "tailoring": 0.35, "beauty_parlour": 0.8},
    "varanasi": {"handloom_weaving": 3.0, "tea_snack_stall": 1.4, "mobile_repair": 1.2, "carpet_weaving": 1.5},
    "mirzapur": {"carpet_weaving": 2.5, "fisheries_pond": 1.3, "handloom_weaving": 1.5},
    "jaunpur": {"tailoring": 1.1, "dairy_farming": 1.2, "carpet_weaving": 1.3},
    "prayagraj": {"fisheries_pond": 1.4, "tea_snack_stall": 1.2, "mustard_oil_mill": 1.3},
    "gaya": {"handloom_weaving": 2.5, "tea_snack_stall": 1.5, "goat_rearing": 1.3},
    "muzaffarpur": {"beekeeping": 4.0, "food_processing_home": 1.6, "poultry_backyard": 1.2},
    "nashik": {"agri_input_depot": 2.2, "dairy_farming": 1.5, "grocery_kirana": 1.1, "poultry_layer": 1.8, "goat_rearing": 1.3},
    "dharwad": {"dairy_farming": 1.3, "food_processing_home": 1.4, "agri_input_depot": 1.3, "handloom_weaving": 0.6},
}
# Within a district, clustered crafts concentrate in these blocks (x1.3) and thin out elsewhere (x0.8)
CLUSTER_BLOCKS = {
    "bhadohi": {"blocks": ["Gyanpur", "Bhadohi", "Aurai"], "activities": ["carpet_weaving", "handloom_weaving"]},
    "varanasi": {"blocks": ["Kashi Vidyapeeth", "Cholapur", "Baragaon"], "activities": ["handloom_weaving"]},
    "gaya": {"blocks": ["Manpur", "Tekari"], "activities": ["handloom_weaving"]},
    "muzaffarpur": {"blocks": ["Kanti", "Mushahari", "Bochaha"], "activities": ["beekeeping"]},
}

# Share of enterprises that appear in a Udyam extract, by catalog sector
REG_RATE = {"animal_husbandry": 0.08, "fisheries": 0.10, "agri_allied": 0.12, "food_processing": 0.35,
            "retail_trade": 0.22, "textiles_apparel": 0.30, "services": 0.18}

PRICE_SERIES = {
    "Wheat": {"trend": 0.05, "season": [1.06, 1.08, 1.03, 0.92, 0.90, 0.95, 0.98, 1.00, 1.01, 1.02, 1.03, 1.05],
              "states": {"Uttar Pradesh": 2250, "Bihar": 2200, "Maharashtra": 2600}},
    "Mustard": {"trend": 0.03, "season": [1.02, 1.00, 0.93, 0.90, 0.95, 1.00, 1.03, 1.04, 1.04, 1.03, 1.02, 1.03],
                "states": {"Uttar Pradesh": 5400, "Bihar": 5500}},
    "Goat": {"trend": 0.07, "season": [0.98, 0.97, 0.98, 0.99, 1.00, 1.03, 0.99, 0.98, 1.00, 1.05, 1.06, 1.00],
             "events": [(2024, 6), (2025, 6), (2026, 5)],  # Bakrid demand spikes
             "states": {"Uttar Pradesh": 32000, "Bihar": 30000, "Maharashtra": 36000, "Karnataka": 35000}},
    "Fish": {"trend": 0.05, "season": [0.94, 0.95, 0.97, 1.00, 1.03, 1.08, 1.10, 1.06, 1.00, 0.97, 0.95, 0.95],
             "states": {"Uttar Pradesh": 14000, "Bihar": 15500, "Maharashtra": 13000, "Karnataka": 12500}},
    "Honey": {"trend": 0.04, "season": [1.00, 0.97, 0.93, 0.92, 0.95, 1.00, 1.03, 1.05, 1.05, 1.04, 1.03, 1.02],
              "states": {"Uttar Pradesh": 22000, "Bihar": 20000, "Maharashtra": 26000}},
}


def _fb(i, kind, district, activity, topic, rating, en, hi, who_en, who_hi, months=None):
    rec = {"id": f"fb_{district}_{i}", "kind": kind, "district": district, "activityId": activity, "topic": topic,
           "rating": rating, "text": {"en": en, "hi": hi}, "who": {"en": who_en, "hi": who_hi}}
    if months is not None:
        rec["monthsInBusiness"] = months
    return rec


F, R = "funded_entrepreneur", "resident_survey"
FEEDBACK = [
    _fb(1, F, "bhadohi", "handloom_weaving", "competition", 2,
        "There is a loom in almost every lane around Gopiganj. Traders set the price and job-work rates have not gone up in two years.",
        "गोपीगंज के आसपास लगभग हर गली में करघा है। व्यापारी दाम तय करते हैं और दो साल से बुनाई की मज़दूरी नहीं बढ़ी।",
        "Handloom weaver, Gyanpur block", "हथकरघा बुनकर, ज्ञानपुर ब्लॉक", 30),
    _fb(2, F, "bhadohi", "carpet_weaving", "supply", 3,
        "Wool yarn got costlier this year and exporters pay us 60 to 90 days late, so money stays stuck.",
        "इस साल ऊनी धागा महँगा हुआ और निर्यातक 60 से 90 दिन देर से भुगतान करते हैं, इसलिए पैसा फँसा रहता है।",
        "Carpet unit owner, Aurai block", "कालीन इकाई मालिक, औराई ब्लॉक", 42),
    _fb(3, R, "bhadohi", "tailoring", "demand", None,
        "It is hard to get blouses and school uniforms stitched near Gopiganj. We go to Gyanpur and wait a week.",
        "गोपीगंज के पास ब्लाउज़ और स्कूल ड्रेस सिलवाना मुश्किल है। ज्ञानपुर जाकर एक हफ़्ता इंतज़ार करना पड़ता है।",
        "Resident survey, Gopiganj (women's group)", "निवासी सर्वे, गोपीगंज (महिला समूह)"),
    _fb(4, F, "bhadohi", "tailoring", "seasonality", 4,
        "Wedding season and school reopening keep my machine busy. There are only two tailors in my village.",
        "शादी के मौसम और स्कूल खुलने पर मशीन खूब चलती है। मेरे गाँव में सिर्फ़ दो दर्ज़ी हैं।",
        "Tailor, Abholi block", "दर्ज़ी, अभोली ब्लॉक", 14),
    _fb(5, R, "bhadohi", "beauty_parlour", "demand", None,
        "Women want a parlour nearby for weddings; the closest one is in Bhadohi town.",
        "शादियों के लिए महिलाएँ पास में पार्लर चाहती हैं; सबसे नज़दीकी भदोही शहर में है।",
        "Resident survey, Suriyawan", "निवासी सर्वे, सुरियावां"),

    _fb(1, F, "varanasi", "handloom_weaving", "competition", 2,
        "Powerloom sarees sold as Banarasi undercut our prices. Only real silk buyers pay for handloom now.",
        "बनारसी के नाम पर बिकने वाली पावरलूम साड़ियाँ हमारे दाम गिरा देती हैं। अब सिर्फ़ असली रेशम के ग्राहक हथकरघा का दाम देते हैं।",
        "Silk weaver, Cholapur block", "रेशम बुनकर, चोलापुर ब्लॉक", 60),
    _fb(2, F, "varanasi", "tea_snack_stall", "seasonality", 4,
        "Sales double from October to March with pilgrims and tourists; summer afternoons are slow.",
        "अक्टूबर से मार्च तक तीर्थयात्रियों और पर्यटकों से बिक्री दोगुनी होती है; गर्मी की दोपहर में धंधा धीमा रहता है।",
        "Tea stall owner, Kashi Vidyapeeth", "चाय स्टॉल मालिक, काशी विद्यापीठ", 22),
    _fb(3, R, "varanasi", "tailoring", "pricing", None,
        "A blouse costs 250 to 350 rupees to stitch in town; people in villages would pay 150 to 200 nearby.",
        "शहर में ब्लाउज़ सिलाई 250 से 350 रुपये है; गाँव में लोग पास में 150 से 200 रुपये देंगे।",
        "Resident survey, Pindra", "निवासी सर्वे, पिंडरा"),
    _fb(4, F, "varanasi", "mobile_repair", "competition", 3,
        "Every market has three or four repair counters. Screen and battery jobs still bring steady work.",
        "हर बाज़ार में तीन-चार रिपेयर काउंटर हैं। स्क्रीन और बैटरी का काम फिर भी लगातार आता है।",
        "Mobile repair shop, Harahua", "मोबाइल रिपेयर दुकान, हरहुआ", 18),

    _fb(1, F, "mirzapur", "carpet_weaving", "demand", 2,
        "Export orders dropped last year; looms sat idle for three months.",
        "पिछले साल निर्यात के ऑर्डर घट गए; तीन महीने करघे खाली पड़े रहे।",
        "Carpet weaver, Majhawan block", "कालीन बुनकर, मझवां ब्लॉक", 36),
    _fb(2, F, "mirzapur", "fisheries_pond", "seasonality", 4,
        "Fish sells best during the monsoon months when river catch is low; ponds need lime before stocking.",
        "बरसात में नदी की मछली कम आती है तब तालाब की मछली सबसे अच्छी बिकती है; बीज डालने से पहले चूना ज़रूरी है।",
        "Pond fish farmer, Kon block", "तालाब मछली पालक, कोन ब्लॉक", 26),
    _fb(3, R, "mirzapur", "grocery_kirana", "demand", None,
        "Hill villages have to walk to the weekly haat for basics; a small store would help.",
        "पहाड़ी गाँवों के लोगों को ज़रूरी सामान के लिए साप्ताहिक हाट तक पैदल जाना पड़ता है; छोटी दुकान से मदद होगी।",
        "Resident survey, Halia", "निवासी सर्वे, हलिया"),

    _fb(1, F, "jaunpur", "dairy_farming", "pricing", 3,
        "The cooperative pays by fat content; in summer the rate falls and fodder gets expensive.",
        "सहकारी समिति फैट के हिसाब से दाम देती है; गर्मी में दाम घटता है और चारा महँगा हो जाता है।",
        "Dairy farmer, Badlapur block", "डेयरी किसान, बदलापुर ब्लॉक", 40),
    _fb(2, F, "jaunpur", "tailoring", "competition", 3,
        "Shahganj market already has many tailors; I get work mainly from my own and nearby villages.",
        "शाहगंज बाज़ार में पहले से कई दर्ज़ी हैं; मुझे ज़्यादातर काम अपने और आसपास के गाँवों से मिलता है।",
        "Tailor, Shahganj block", "दर्ज़ी, शाहगंज ब्लॉक", 20),
    _fb(3, R, "jaunpur", "food_processing_home", "demand", None,
        "Homemade pickles sell well at fairs and to families working in cities.",
        "घर के बने अचार मेलों में और शहरों में काम करने वाले परिवारों को अच्छे बिकते हैं।",
        "Resident survey, Kerakat", "निवासी सर्वे, केराकत"),

    _fb(1, F, "prayagraj", "fisheries_pond", "demand", 4,
        "Demand and prices jump during the Magh Mela months; transport to the city market is easy.",
        "माघ मेले के महीनों में माँग और दाम बढ़ जाते हैं; शहर की मंडी तक ले जाना आसान है।",
        "Fish farmer, Karchhana block", "मछली पालक, करछना ब्लॉक", 28),
    _fb(2, F, "prayagraj", "tea_snack_stall", "seasonality", 3,
        "Crowds come in January and February; the rest of the year depends on the bus stand traffic.",
        "जनवरी-फ़रवरी में भीड़ आती है; बाकी साल बस स्टैंड की आवाजाही पर निर्भर है।",
        "Snack stall owner, Phulpur", "नाश्ता स्टॉल मालिक, फूलपुर", 16),
    _fb(3, R, "prayagraj", "dairy_farming", "supply", None,
        "Milk is short in summer and families buy packet milk from town.",
        "गर्मी में दूध कम पड़ता है और परिवार शहर से पैकेट वाला दूध खरीदते हैं।",
        "Resident survey, Soraon", "निवासी सर्वे, सोरांव"),

    _fb(1, F, "gaya", "handloom_weaving", "competition", 2,
        "Manpur has thousands of looms; margins are thin unless you sell directly to shops.",
        "मानपुर में हज़ारों करघे हैं; सीधे दुकानों को बेचे बिना मुनाफ़ा बहुत कम है।",
        "Weaver, Manpur (Patwatoli)", "बुनकर, मानपुर (पटवाटोली)", 50),
    _fb(2, F, "gaya", "tea_snack_stall", "seasonality", 4,
        "From October to March visitors to Bodh Gaya keep the stall busy; summer is quiet.",
        "अक्टूबर से मार्च तक बोधगया आने वाले यात्रियों से स्टॉल चलता है; गर्मी में सन्नाटा रहता है।",
        "Tea stall owner, Bodh Gaya", "चाय स्टॉल मालिक, बोधगया", 24),
    _fb(3, F, "gaya", "goat_rearing", "pricing", 4,
        "Goats fetch the best price before Bakrid; I sell half my stock in that month.",
        "बकरीद से पहले बकरियों का सबसे अच्छा दाम मिलता है; मैं उसी महीने आधे जानवर बेचती हूँ।",
        "Goat rearer (SHG member), Tekari block", "बकरी पालक (स्वयं सहायता समूह सदस्य), टेकारी ब्लॉक", 32),
    _fb(4, R, "gaya", "tailoring", "demand", None,
        "School uniforms and petticoats are always needed; there is only one tailor near Gopiganj.",
        "स्कूल ड्रेस और पेटीकोट की ज़रूरत हमेशा रहती है; गोपीगंज के पास सिर्फ़ एक दर्ज़ी है।",
        "Resident survey, Tekari", "निवासी सर्वे, टेकारी"),

    _fb(1, F, "muzaffarpur", "beekeeping", "seasonality", 4,
        "Litchi flowering in February and March gives the main honey flow; boxes must move after that.",
        "फ़रवरी-मार्च में लीची के फूल से मुख्य शहद मिलता है; उसके बाद बक्से दूसरी जगह ले जाने पड़ते हैं।",
        "Beekeeper, Kanti block", "मधुमक्खी पालक, कांटी ब्लॉक", 38),
    _fb(2, F, "muzaffarpur", "food_processing_home", "demand", 4,
        "Litchi squash and pickles sell out in summer; packaging material comes from Patna.",
        "गर्मी में लीची शरबत और अचार खत्म हो जाते हैं; पैकिंग सामान पटना से आता है।",
        "Home food unit, Mushahari", "घरेलू खाद्य इकाई, मुसहरी", 19),
    _fb(3, F, "muzaffarpur", "poultry_backyard", "supply", 3,
        "Feed prices went up and chicks from the hatchery sometimes arrive late.",
        "दाने के दाम बढ़ गए और हैचरी से चूज़े कभी-कभी देर से आते हैं।",
        "Poultry rearer, Sakra block", "मुर्गी पालक, सकरा ब्लॉक", 15),
    _fb(4, R, "muzaffarpur", "grocery_kirana", "competition", None,
        "Our village already has four kirana shops; people buy bulk items in town.",
        "हमारे गाँव में पहले से चार किराना दुकानें हैं; लोग थोक सामान शहर से लाते हैं।",
        "Resident survey, Motipur", "निवासी सर्वे, मोतीपुर"),

    _fb(1, F, "nashik", "agri_input_depot", "competition", 3,
        "Grape and onion farmers buy on credit; recovering dues after a bad harvest is hard.",
        "अंगूर और प्याज़ किसान उधार पर खरीदते हैं; खराब फ़सल के बाद बकाया वसूलना मुश्किल है।",
        "Agri input dealer, Niphad", "कृषि सामग्री विक्रेता, निफाड", 48),
    _fb(2, F, "nashik", "dairy_farming", "pricing", 3,
        "Private dairies change the milk rate every few weeks; cattle feed is the biggest cost.",
        "निजी डेयरियाँ हर कुछ हफ़्तों में दूध का दाम बदलती हैं; पशु आहार सबसे बड़ा खर्च है।",
        "Dairy farmer, Sinnar", "डेयरी किसान, सिन्नर", 34),
    _fb(3, F, "nashik", "poultry_layer", "supply", 3,
        "Layer feed and vaccine supply is good near Nashik, but egg prices fall in the monsoon.",
        "नासिक के पास लेयर दाना और टीके आसानी से मिलते हैं, पर बरसात में अंडे के दाम गिरते हैं।",
        "Layer farm owner, Dindori", "लेयर फ़ार्म मालिक, दिंडोरी", 27),
    _fb(4, R, "nashik", "mobile_repair", "demand", None,
        "Farm workers need phones fixed fast; the nearest repair shop is 12 km away.",
        "खेत मज़दूरों को फ़ोन जल्दी ठीक चाहिए; सबसे नज़दीकी रिपेयर दुकान 12 किमी दूर है।",
        "Resident survey, Igatpuri", "निवासी सर्वे, इगतपुरी"),

    _fb(1, F, "dharwad", "dairy_farming", "demand", 4,
        "Pedha makers in Dharwad buy all the milk we produce, and they pay weekly.",
        "धारवाड़ के पेड़ा बनाने वाले हमारा सारा दूध खरीदते हैं और हर हफ़्ते भुगतान करते हैं।",
        "Dairy farmer, Kundgol", "डेयरी किसान, कुंदगोल", 44),
    _fb(2, F, "dharwad", "food_processing_home", "pricing", 3,
        "Shops take our snacks on consignment; the margin is fair but payment comes after sale.",
        "दुकानें हमारे नाश्ते उधारी पर रखती हैं; मुनाफ़ा ठीक है पर पैसा बिकने के बाद मिलता है।",
        "Snack maker (SHG), Hubli", "नाश्ता निर्माता (स्वयं सहायता समूह), हुबली", 21),
    _fb(3, R, "dharwad", "beauty_parlour", "demand", None,
        "Young women travel to Hubli for bridal makeup; a parlour in Kalghatgi would get customers.",
        "युवतियाँ दुल्हन मेकअप के लिए हुबली जाती हैं; कलघटगी में पार्लर को ग्राहक मिलेंगे।",
        "Resident survey, Kalghatgi", "निवासी सर्वे, कलघटगी"),
    _fb(4, F, "dharwad", "agri_input_depot", "seasonality", 3,
        "Sales peak before kharif sowing in June and rabi in October; stock sits idle in between.",
        "जून में खरीफ़ और अक्टूबर में रबी बुवाई से पहले बिक्री चरम पर होती है; बीच में माल पड़ा रहता है।",
        "Seed and fertiliser depot, Navalgund", "बीज-खाद डिपो, नवलगुंद", 29),
]

"""
MASA V2 — Market Stock Data
Saudi Market (TASI) + US Market (S&P 500) + Forex (20 pairs) + Crypto (10 coins)
"""

SAUDI_STOCKS = {
    # ══════════════════════════════════════════════════════════
    # المصارف والخدمات المالية (Banks & Financial Services)
    # ══════════════════════════════════════════════════════════
    "1010.SR": "الرياض",
    "1020.SR": "الجزيرة",
    "1030.SR": "الاستثمار",
    "1050.SR": "السعودي الفرنسي",
    "1060.SR": "الأول",
    "1080.SR": "العربي",
    "1111.SR": "تداول",
    "1120.SR": "الراجحي",
    "1140.SR": "البلاد",
    "1150.SR": "الإنماء",
    "1180.SR": "الأهلي",
    "1182.SR": "أملاك",
    "1183.SR": "سهل",
    # ══════════════════════════════════════════════════════════
    # المواد الأساسية (Materials & Mining)
    # ══════════════════════════════════════════════════════════
    "1201.SR": "تكوين",
    "1202.SR": "مبكو",
    "1210.SR": "بي سي آي",
    "1211.SR": "معادن",
    "1212.SR": "أسترا الصناعية",
    "1213.SR": "نسيج",
    "1214.SR": "شاكر",
    "1301.SR": "أسلاك",
    "1302.SR": "بوان",
    "1303.SR": "الصناعات الكهربائية",
    "1304.SR": "اليمامة للحديد",
    "1320.SR": "أنابيب السعودية",
    "1321.SR": "أنابيب الشرق",
    "1322.SR": "أماك",
    "1323.SR": "الكرتون المتحدة",
    "1324.SR": "صالح الراشد",
    # ══════════════════════════════════════════════════════════
    # الشركات القابضة والخدمات (Diversified Holdings & Services)
    # ══════════════════════════════════════════════════════════
    "1810.SR": "سيرا القابضة",
    "1820.SR": "بان القابضة",
    "1830.SR": "لجام للرياضة",
    "1831.SR": "مهارة للموارد",
    "1832.SR": "صدر",
    "1833.SR": "الموارد",
    "1834.SR": "حلول القوى",
    "1835.SR": "تمكين",
    # ══════════════════════════════════════════════════════════
    # البتروكيماويات والطاقة (Petrochemicals & Energy)
    # ══════════════════════════════════════════════════════════
    "2001.SR": "كيمانول",
    "2010.SR": "سابك",
    "2020.SR": "المغذيات",
    "2030.SR": "المصافي",
    "2040.SR": "الخزف السعودي",
    "2050.SR": "مجموعة صافولا",
    "2060.SR": "التصنيع",
    "2070.SR": "الدوائية",
    "2080.SR": "الغاز",
    "2081.SR": "الخريف",
    "2082.SR": "أكوا باور",
    "2083.SR": "مرافق",
    "2084.SR": "مياهنا",
    "2090.SR": "الجبس الوطنية",
    "2100.SR": "وفرة",
    "2110.SR": "الكابلات",
    "2120.SR": "المتطورة",
    "2130.SR": "صدق",
    "2140.SR": "أميانتيت",
    "2150.SR": "زجاج",
    "2160.SR": "أميانتيت السعودية",
    "2170.SR": "اللجين",
    "2180.SR": "فيبكو",
    "2190.SR": "سيسكو",
    "2200.SR": "أنابيب",
    "2210.SR": "نماء",
    "2220.SR": "معدنية",
    "2222.SR": "أرامكو",
    "2223.SR": "لوبريف",
    "2230.SR": "الكيميائية",
    "2240.SR": "الزامل",
    "2250.SR": "المجموعة السعودية",
    "2270.SR": "سدافكو",
    "2280.SR": "المراعي",
    "2281.SR": "تنمية",
    "2282.SR": "المطاحن الأولى",
    "2283.SR": "المطاحن الحديثة",
    "2284.SR": "المطاحن العربية",
    "2285.SR": "مطاحن صافية",
    "2286.SR": "المطاحن الرابعة",
    "2287.SR": "رغوة",
    "2288.SR": "نفوذ الغذائية",
    "2290.SR": "ينساب",
    "2300.SR": "صناعة الورق",
    "2310.SR": "سبكيم",
    "2320.SR": "البابطين",
    "2330.SR": "المتقدمة",
    "2340.SR": "العالمية",
    "2350.SR": "كيان السعودية",
    "2360.SR": "الفخارية",
    "2370.SR": "مسك",
    "2380.SR": "بترورابغ",
    "2381.SR": "الحفر العربية",
    "2382.SR": "أديس",
    # ══════════════════════════════════════════════════════════
    # الأسمنت (Cement)
    # ══════════════════════════════════════════════════════════
    "3002.SR": "أسمنت نجران",
    "3003.SR": "أسمنت المدينة",
    "3004.SR": "أسمنت الشمالية",
    "3005.SR": "أسمنت أم القرى",
    "3007.SR": "الواحة",
    "3008.SR": "الكثيري",
    "3010.SR": "أسمنت العربية",
    "3020.SR": "أسمنت اليمامة",
    "3030.SR": "أسمنت السعودية",
    "3040.SR": "أسمنت القصيم",
    "3050.SR": "أسمنت الجنوبية",
    "3060.SR": "أسمنت ينبع",
    "3080.SR": "أسمنت الشرقية",
    "3090.SR": "أسمنت تبوك",
    "3091.SR": "أسمنت الجوف",
    "3092.SR": "أسمنت المدينة المنورة",
    # ══════════════════════════════════════════════════════════
    # التجزئة والرعاية الصحية (Retail & Healthcare)
    # ══════════════════════════════════════════════════════════
    "4001.SR": "أسواق العثيم",
    "4002.SR": "المواساة",
    "4003.SR": "إكسترا",
    "4004.SR": "دله الصحية",
    "4005.SR": "رعاية",
    "4006.SR": "التسويق السعودية",
    "4007.SR": "الحمادي",
    "4008.SR": "ساكو",
    "4009.SR": "السعودي الألماني الصحية",
    "4011.SR": "لازوردي",
    "4012.SR": "ثوب الأصيل",
    "4013.SR": "سليمان الحبيب",
    "4014.SR": "دار المعدات",
    "4015.SR": "جمجوم فارما",
    "4016.SR": "صناعة الأدوية",
    "4017.SR": "فقيه الطبية",
    "4018.SR": "الموسى الصحية",
    "4019.SR": "المتخصصة الطبية",
    "4020.SR": "العقارية",
    "4021.SR": "المركز الكندي الطبي",
    # ══════════════════════════════════════════════════════════
    # النقل والخدمات اللوجستية (Transport & Logistics)
    # ══════════════════════════════════════════════════════════
    "4030.SR": "البحري",
    "4031.SR": "مهارة",
    "4040.SR": "سابتكو",
    "4050.SR": "ساسكو",
    "4051.SR": "بازعيم",
    "4061.SR": "أنعام القابضة",
    "4070.SR": "تهامة",
    "4071.SR": "العربية",
    "4072.SR": "إم بي سي",
    # ══════════════════════════════════════════════════════════
    # الخدمات المالية والاستثمار (Financial Services)
    # ══════════════════════════════════════════════════════════
    "4080.SR": "سيناد القابضة",
    "4081.SR": "النايفات",
    "4082.SR": "مرابحة مارينا",
    "4083.SR": "المتحدة الدولية",
    "4084.SR": "دراية المالية",
    # ══════════════════════════════════════════════════════════
    # السياحة والفنادق والتجزئة (Tourism, Hotels & Retail)
    # ══════════════════════════════════════════════════════════
    "4090.SR": "طيبة",
    "4100.SR": "مكة",
    "4110.SR": "باتك",
    "4130.SR": "درب السعودية",
    "4140.SR": "الصادرات",
    "4141.SR": "العمران",
    "4142.SR": "كابلات الرياض",
    "4143.SR": "التيسير",
    "4144.SR": "روم للتجارة",
    "4145.SR": "العبيكان للزجاج",
    "4146.SR": "خدمات الغاز العربية",
    "4147.SR": "المتكاملة القابضة",
    "4148.SR": "الوسائل الصناعية",
    "4150.SR": "التعمير",
    "4160.SR": "ثمار",
    "4161.SR": "بن داود",
    "4162.SR": "المنجم",
    "4163.SR": "الدواء",
    "4164.SR": "النهدي",
    "4165.SR": "الماجد للعود",
    "4170.SR": "شمس",
    "4180.SR": "مجموعة فتيحي",
    "4190.SR": "جرير",
    "4191.SR": "أبو معطي",
    "4192.SR": "السيف غاليري",
    "4193.SR": "نايس ون",
    "4194.SR": "بيت التسويق",
    "4200.SR": "الدريس",
    "4210.SR": "الأبحاث والإعلام",
    "4220.SR": "إعمار",
    "4230.SR": "البحر الأحمر",
    "4240.SR": "سينومي ريتيل",
    "4250.SR": "جبل عمر",
    "4260.SR": "بدجت",
    "4261.SR": "ذيب",
    "4262.SR": "لومي",
    "4263.SR": "سال للخدمات",
    "4264.SR": "طيران ناس",
    "4265.SR": "كرز للتجارة",
    "4270.SR": "تغليف وتعبئة",
    "4280.SR": "المملكة",
    "4290.SR": "الخليج للتدريب",
    "4291.SR": "التعلم الوطنية",
    "4292.SR": "عطاء التعليمية",
    # ══════════════════════════════════════════════════════════
    # العقار وصناديق الريت (Real Estate & REITs)
    # ══════════════════════════════════════════════════════════
    "4300.SR": "دار الأركان",
    "4310.SR": "اقتصادية المعرفة",
    "4320.SR": "الأندلس",
    "4321.SR": "سينومي سنترز",
    "4322.SR": "ريتال",
    "4323.SR": "سمو العقارية",
    "4324.SR": "بنان العقارية",
    "4325.SR": "أم القرى للتطوير",
    "4326.SR": "دار المجد",
    "4327.SR": "الرمز العقارية",
    # ══════════════════════════════════════════════════════════
    # المرافق العامة (Utilities)
    # ══════════════════════════════════════════════════════════
    "5110.SR": "الكهرباء",
    # ══════════════════════════════════════════════════════════
    # الزراعة والغذاء (Food & Agriculture)
    # ══════════════════════════════════════════════════════════
    "6001.SR": "حلواني إخوان",
    "6002.SR": "هرفي",
    "6004.SR": "كاتريون",
    "6010.SR": "نادك",
    "6012.SR": "ريدان",
    "6013.SR": "التطويرية الغذائية",
    "6014.SR": "الآمار",
    "6015.SR": "أمريكانا",
    "6016.SR": "شاورمر",
    "6017.SR": "جاهز",
    "6018.SR": "أندية رياضية",
    "6019.SR": "المسار الشامل",
    "6020.SR": "القصيم",
    "6040.SR": "تبوك الزراعية",
    "6050.SR": "الأسماك",
    "6060.SR": "الشرقية للتنمية",
    "6070.SR": "الجوف",
    "6090.SR": "جازادكو",
    # ══════════════════════════════════════════════════════════
    # الاتصالات (Telecom)
    # ══════════════════════════════════════════════════════════
    "7010.SR": "STC",
    "7020.SR": "موبايلي",
    "7030.SR": "زين السعودية",
    "7040.SR": "قو للاتصالات",
    # ══════════════════════════════════════════════════════════
    # التقنية (Technology)
    # ══════════════════════════════════════════════════════════
    "7200.SR": "ام آي اس",
    "7201.SR": "بحر العرب",
    "7202.SR": "سلوشنز",
    "7203.SR": "علم",
    "7204.SR": "توبي",
    "7211.SR": "عزم",
    # ══════════════════════════════════════════════════════════
    # التأمين (Insurance)
    # ══════════════════════════════════════════════════════════
    "8010.SR": "التعاونية",
    "8012.SR": "الجزيرة تكافل",
    "8020.SR": "ملاذ للتأمين",
    "8030.SR": "ميدغلف",
    "8040.SR": "أليانز",
    "8050.SR": "سلامة",
    "8060.SR": "ولاء",
    "8070.SR": "الدرع العربي",
    "8100.SR": "سايكو",
    "8120.SR": "اتحاد الخليج",
    "8150.SR": "أسيج",
    "8160.SR": "التأمين العربية",
    "8170.SR": "الاتحاد للتأمين",
    "8180.SR": "الصقر للتأمين",
    "8190.SR": "المتحدة للتأمين",
    "8200.SR": "إعادة",
    "8210.SR": "بوبا",
    "8230.SR": "تكافل الراجحي",
    "8240.SR": "تشب",
    "8250.SR": "عناية",
    "8260.SR": "أمانة للتأمين",
    "8280.SR": "ليفا",
    "8300.SR": "الوطنية للتأمين",
    "8310.SR": "أمانة للتأمين التعاوني",
    "8311.SR": "عناية السعودية",
    "8313.SR": "رسن",
}


# ══════════════════════════════════════════════════════════════
# US Market — S&P 500 Top 200+ Stocks
# ══════════════════════════════════════════════════════════════

US_STOCKS = {
    # ═══════════════════════════════════════════
    # 1. Communication Services
    # ═══════════════════════════════════════════
    # Internet Content & Information
    "GOOG": "Alphabet (Google)",
    "GOOGL": "Alphabet Class A",
    "META": "Meta (Facebook)",
    "BIDU": "Baidu",
    "NTES": "NetEase",
    "RDDT": "Reddit",

    # Entertainment - Streaming & Media
    "NFLX": "Netflix",
    "DIS": "Walt Disney",
    "SPOT": "Spotify",
    "ROKU": "Roku",
    "WBD": "Warner Bros Discovery",

    # Entertainment - Gaming
    "EA": "Electronic Arts",
    "TTWO": "Take-Two Interactive",
    "RBLX": "Roblox",

    # Entertainment - Live Events & Music
    "LYV": "Live Nation Entertainment",
    "TKO": "TKO Group Holdings",
    "WMG": "Warner Music Group",
    "FWONA": "Liberty Media F1 Class A",
    "FWONK": "Liberty Media F1 Class C",

    # Telecom Services - US
    "TMUS": "T-Mobile US",
    "VZ": "Verizon",
    "T": "AT&T",

    # Telecom Services - International
    "AMX": "América Móvil",
    "VOD": "Vodafone",
    "CHT": "Chunghwa Telecom",
    "BCE": "BCE Inc.",
    "RCI": "Rogers Communications",
    "TU": "TELUS",
    "TLK": "Telkom Indonesia",
    "VIV": "Telefônica Brasil",
    "TIGO": "Millicom",

    # Pay TV & Broadcasting
    "CMCSA": "Comcast",
    "CHTR": "Charter Communications",
    "FOX": "Fox Corporation",
    "FOXA": "Fox Corporation A",

    # Publishing
    "NWSA": "News Corp A",
    "NWS": "News Corp",

    # Advertising
    "APP": "AppLovin",
    "OMC": "Omnicom Group",

    # Communication Equipment & Satellites
    "SATS": "EchoStar",

    # ═══════════════════════════════════════════
    # 2. Consumer Defensive
    # ═══════════════════════════════════════════
    # Discount Stores
    "WMT": "Walmart",
    "COST": "Costco",
    "TGT": "Target",
    "DG": "Dollar General",
    "DLTR": "Dollar Tree",
    "BJ": "BJ's Wholesale",

    # Grocery
    "KR": "Kroger",
    "ACI": "Albertsons",
    "SFM": "Sprouts Farmers Market",
    "CASY": "Casey's",

    # Beverages - Non-Alcoholic
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
    "MNST": "Monster Beverage",
    "KDP": "Keurig Dr Pepper",
    "CELH": "Celsius Holdings",
    "CCEP": "Coca-Cola Europacific",

    # Packaged Foods
    "MDLZ": "Mondelez",
    "GIS": "General Mills",
    "K": "Kellanova",
    "CPB": "Campbell's",
    "MKC": "McCormick",
    "SJM": "J.M. Smucker",
    "BG": "Bunge Global",
    "ADM": "Archer-Daniels-Midland",
    "CALM": "Cal-Maine Foods",
    "BYND": "Beyond Meat",

    # Household & Personal Products
    "PG": "Procter & Gamble",
    "UL": "Unilever",
    "CL": "Colgate-Palmolive",
    "KMB": "Kimberly-Clark",
    "CHD": "Church & Dwight",
    "CLX": "Clorox",
    "EL": "Estée Lauder",

    # Confectioners
    "HSY": "Hershey",
    "TR": "Tootsie Roll",

    # Agricultural Products
    "AGRO": "Adecoagro",
    "ANDE": "Andersons",

    # ═══════════════════════════════════════════
    # 3. Consumer Discretionary
    # ═══════════════════════════════════════════
    # Internet Retail
    "AMZN": "Amazon",
    "BABA": "Alibaba",
    "MELI": "MercadoLibre",
    "PDD": "PDD Holdings (Temu)",
    "EBAY": "eBay",
    "ETSY": "Etsy",
    "CHWY": "Chewy",
    "W": "Wayfair",
    "CVNA": "Carvana",

    # Specialty Retail
    "HD": "Home Depot",
    "LOW": "Lowe's",
    "TJX": "TJX Companies",
    "ROST": "Ross Stores",
    "BURL": "Burlington Stores",
    "ULTA": "Ulta Beauty",
    "BBY": "Best Buy",
    "DKS": "Dick's Sporting Goods",
    "AZO": "AutoZone",
    "ORLY": "O'Reilly Automotive",
    "AAP": "Advance Auto Parts",
    "TSCO": "Tractor Supply",
    "FND": "Floor & Decor",
    "WSM": "Williams-Sonoma",
    "RH": "RH (Restoration Hardware)",
    "ASO": "Academy Sports",

    # Apparel - Manufacturers
    "NKE": "Nike",
    "LULU": "Lululemon Athletica",
    "DECK": "Deckers Outdoor",
    "VFC": "VF Corporation",
    "ONON": "On Holding",
    "BIRK": "Birkenstock",
    "CROX": "Crocs",
    "SKX": "Skechers",
    "COLM": "Columbia Sportswear",

    # Apparel - Retail
    "AEO": "American Eagle",
    "ANF": "Abercrombie & Fitch",
    "URBN": "Urban Outfitters",
    "GAP": "Gap Inc.",

    # Luxury Goods
    "LVMUY": "LVMH",
    "CFRUY": "Richemont",
    "KER": "Kering",
    "CPRI": "Capri Holdings",
    "TPR": "Tapestry",

    # Auto Manufacturers
    "TSLA": "Tesla",
    "TM": "Toyota Motor",
    "F": "Ford Motor",
    "GM": "General Motors",
    "HMC": "Honda Motor",
    "STLA": "Stellantis",
    "RIVN": "Rivian Automotive",
    "LCID": "Lucid Group",
    "LI": "Li Auto",
    "NIO": "NIO Inc.",
    "XPEV": "XPeng",
    "BYDDY": "BYD",

    # Auto Parts
    "APTV": "Aptiv",
    "LEA": "Lear",
    "BWA": "BorgWarner",
    "ALV": "Autoliv",
    "ALSN": "Allison Transmission",
    "DAN": "Dana",

    # Auto & Truck Dealerships
    "AN": "AutoNation",
    "LAD": "Lithia Motors",
    "PAG": "Penske Automotive",
    "ABG": "Asbury Automotive",
    "GPI": "Group 1 Automotive",
    "KMX": "CarMax",

    # Home Furnishings
    "LEG": "Leggett & Platt",
    "WHR": "Whirlpool",
    "MHK": "Mohawk Industries",
    "SCS": "Steelcase",

    # Homebuilders
    "DHI": "D.R. Horton",
    "LEN": "Lennar",
    "NVR": "NVR Inc.",
    "PHM": "PulteGroup",
    "TOL": "Toll Brothers",
    "KBH": "KB Home",
    "MTH": "Meritage Homes",

    # Packaging & Containers
    "PKG": "Packaging Corp",
    "IP": "International Paper",
    "BALL": "Ball Corp",
    "AMCR": "Amcor",
    "CCK": "Crown Holdings",
    "AVY": "Avery Dennison",
    "SEE": "Sealed Air",

    # Restaurants & Travel (DoorDash moved here)
    "DASH": "DoorDash",

    # ═══════════════════════════════════════════
    # 4. Energy
    # ═══════════════════════════════════════════
    # Oil & Gas Integrated
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "SHEL": "Shell plc",
    "BP": "BP plc",
    "TTE": "TotalEnergies",
    "EQNR": "Equinor",
    "E": "Eni",
    "PBR": "Petrobras",
    "PBR.A": "Petrobras A",
    "EC": "Ecopetrol",
    "SU": "Suncor Energy",
    "IMO": "Imperial Oil",
    "CNQ": "Canadian Natural Resources",
    "CVE": "Cenovus Energy",

    # Oil & Gas E&P
    "COP": "ConocoPhillips",
    "EOG": "EOG Resources",
    "OXY": "Occidental Petroleum",
    "CTRA": "Coterra Energy",
    "DVN": "Devon Energy",
    "HES": "Hess Corporation",
    "MRO": "Marathon Oil",
    "PXD": "Pioneer Natural Resources",
    "FANG": "Diamondback Energy",
    "APA": "APA Corporation",
    "CHRD": "Chord Energy",
    "MTDR": "Matador Resources",
    "AR": "Antero Resources",
    "SM": "SM Energy",
    "CRC": "California Resources",
    "CRGY": "Crescent Energy",
    "VET": "Vermilion Energy",
    "TPL": "Texas Pacific Land",

    # Oil & Gas Midstream
    "ENB": "Enbridge",
    "ET": "Energy Transfer",
    "EPD": "Enterprise Products Partners",
    "KMI": "Kinder Morgan",
    "WMB": "Williams Companies",
    "OKE": "ONEOK",
    "TRP": "TC Energy",
    "LNG": "Cheniere Energy",
    "MPLX": "MPLX LP",
    "WES": "Western Midstream",
    "PAA": "Plains All American",
    "PAGP": "Plains GP Holdings",
    "TRGP": "Targa Resources",
    "AROC": "Archrock",

    # Oil & Gas Refining & Marketing
    "MPC": "Marathon Petroleum",
    "PSX": "Phillips 66",
    "VLO": "Valero Energy",
    "DINO": "HF Sinclair",
    "PBF": "PBF Energy",

    # Oil & Gas Equipment & Services
    "SLB": "SLB (Schlumberger)",
    "BKR": "Baker Hughes",
    "HAL": "Halliburton",
    "TS": "Tenaris",
    "WFRD": "Weatherford International",
    "CHX": "ChampionX",
    "LBRT": "Liberty Energy",
    "NOV": "NOV Inc.",
    "FTI": "TechnipFMC",
    "ACDC": "ProFrac Holding",
    "CLB": "Core Laboratories",

    # Oil & Gas Drilling
    "RIG": "Transocean",
    "VAL": "Valaris",
    "NE": "Noble Corp",
    "BORR": "Borr Drilling",
    "HP": "Helmerich & Payne",
    "PTEN": "Patterson-UTI Energy",
    "NBR": "Nabors Industries",

    # Thermal Coal
    "BTU": "Peabody Energy",
    "ARLP": "Alliance Resource Partners",
    "AMR": "Alpha Metallurgical Resources",
    "HCC": "Warrior Met Coal",
    "CEIX": "Consol Energy",
    "METC": "Ramaco Resources",

    # Uranium & Nuclear Fuel
    "CCJ": "Cameco",
    "UEC": "Uranium Energy",
    "DNN": "Denison Mines",
    "URG": "Ur-Energy",
    "LEU": "Centrus Energy",
    "BWXT": "BWX Technologies",

    # Renewable Energy (Solar + Wind)
    "BEPC": "Brookfield Renewable Corp",
    "BEP": "Brookfield Renewable LP",
    "FSLR": "First Solar",
    "ENPH": "Enphase Energy",
    "SEDG": "SolarEdge",
    "RUN": "Sunrun",
    "NOVA": "Sunnova Energy",
    "ARRY": "Array Technologies",
    "SHLS": "Shoals Technologies",
    "CWEN": "Clearway Energy",

    # Solar Manufacturing
    "JKS": "JinkoSolar",
    "CSIQ": "Canadian Solar",
    "DQ": "Daqo New Energy",
    "SOL": "Emeren Group",
    "MAXN": "Maxeon Solar",

    # ═══════════════════════════════════════════
    # 5. Healthcare
    # ═══════════════════════════════════════════
    # Drug Manufacturers - General
    "LLY": "Eli Lilly",
    "JNJ": "Johnson & Johnson",
    "NVO": "Novo Nordisk",
    "ABBV": "AbbVie",
    "MRK": "Merck & Co",
    "AZN": "AstraZeneca",
    "PFE": "Pfizer",
    "NVS": "Novartis",
    "BMY": "Bristol-Myers Squibb",
    "GSK": "GlaxoSmithKline",
    "SNY": "Sanofi",
    "TAK": "Takeda",

    # Biotechnology
    "AMGN": "Amgen",
    "VRTX": "Vertex Pharmaceuticals",
    "GILD": "Gilead Sciences",
    "REGN": "Regeneron Pharmaceuticals",
    "BIIB": "Biogen",
    "MRNA": "Moderna",
    "BNTX": "BioNTech",
    "ALNY": "Alnylam Pharmaceuticals",
    "ARGX": "argenx",

    # Medical Devices
    "ABT": "Abbott Laboratories",
    "ISRG": "Intuitive Surgical",
    "SYK": "Stryker",
    "MDT": "Medtronic",
    "BSX": "Boston Scientific",
    "BDX": "Becton Dickinson",
    "EW": "Edwards Lifesciences",
    "ZBH": "Zimmer Biomet",

    # Medical Instruments & Supplies
    "DXCM": "DexCom",
    "PODD": "Insulet",
    "ALC": "Alcon",
    "COO": "Cooper Companies",

    # Diagnostics & Research
    "TMO": "Thermo Fisher Scientific",
    "DHR": "Danaher",
    "A": "Agilent Technologies",
    "IQV": "IQVIA Holdings",
    "MTD": "Mettler-Toledo",
    "WAT": "Waters Corporation",
    "IDXX": "IDEXX Laboratories",
    "LH": "Labcorp Holdings",
    "DGX": "Quest Diagnostics",

    # Healthcare Plans
    "UNH": "UnitedHealth Group",
    "ELV": "Elevance Health",
    "CI": "Cigna Group",
    "HUM": "Humana",
    "CNC": "Centene Corporation",

    # Medical Care Facilities
    "HCA": "HCA Healthcare",
    "THC": "Tenet Healthcare",
    "UHS": "Universal Health Services",
    "DVA": "DaVita",

    # Medical Distribution
    "MCK": "McKesson",
    "COR": "Cencora",
    "CAH": "Cardinal Health",

    # Pharmaceutical Retailers
    "CVS": "CVS Health",
    "WBA": "Walgreens Boots Alliance",

    # Health Information Services
    "VEEV": "Veeva Systems",

    # ═══════════════════════════════════════════
    # 6. Industrials
    # ═══════════════════════════════════════════
    # Aerospace & Defense
    "RTX": "RTX Corporation",
    "BA": "Boeing",
    "LMT": "Lockheed Martin",
    "GD": "General Dynamics",
    "NOC": "Northrop Grumman",
    "LHX": "L3Harris Technologies",
    "TDG": "TransDigm Group",
    "HWM": "Howmet Aerospace",

    # Heavy Machinery & Construction Equipment
    "CAT": "Caterpillar",
    "DE": "Deere & Company",
    "CMI": "Cummins",
    "PCAR": "PACCAR",
    "URI": "United Rentals",

    # Industrial Conglomerates
    "GE": "GE Aerospace",
    "HON": "Honeywell",
    "MMM": "3M",
    "ITW": "Illinois Tool Works",
    "GEV": "GE Vernova",

    # Electrical Equipment & Power
    "ETN": "Eaton",
    "VRT": "Vertiv Holdings",
    "PWR": "Quanta Services",
    "EMR": "Emerson Electric",
    "BE": "Bloom Energy",

    # Industrial Distribution
    "GWW": "W.W. Grainger",

    # Specialty Industrial Machinery
    "PH": "Parker Hannifin",
    "TT": "Trane Technologies",
    "CARR": "Carrier Global",
    "FIX": "Comfort Systems USA",

    # Railroads
    "UNP": "Union Pacific",
    "CSX": "CSX Corp",
    "NSC": "Norfolk Southern",
    "CNI": "Canadian National Railway",
    "CP": "Canadian Pacific Kansas City",

    # Trucking & Logistics
    "UPS": "United Parcel Service",
    "FDX": "FedEx",

    # Waste Management
    "WM": "Waste Management",
    "RSG": "Republic Services",

    # Building Products
    "JCI": "Johnson Controls",

    # Business Services
    "CTAS": "Cintas",
    "RELX": "RELX Group",

    # ═══════════════════════════════════════════
    # 7. Information Technology
    # ═══════════════════════════════════════════
    # Semiconductors
    "NVDA": "NVIDIA",
    "AVGO": "Broadcom",
    "TSM": "Taiwan Semiconductor",
    "AMD": "Advanced Micro Devices",
    "QCOM": "Qualcomm",
    "TXN": "Texas Instruments",
    "ARM": "Arm Holdings",
    "MU": "Micron Technology",
    "ADI": "Analog Devices",
    "LRCX": "Lam Research",
    "KLAC": "KLA Corporation",
    "AMAT": "Applied Materials",
    "ASML": "ASML Holding",
    "MRVL": "Marvell Technology",
    "MCHP": "Microchip Technology",
    "ON": "ON Semiconductor",
    "NXPI": "NXP Semiconductors",
    "ASX": "ASE Technology",
    "UMC": "United Microelectronics",
    "ALAB": "Astera Labs",

    # Software - Infrastructure
    "MSFT": "Microsoft",
    "ORCL": "Oracle",
    "ADBE": "Adobe",
    "PANW": "Palo Alto Networks",
    "CRWD": "CrowdStrike",
    "FTNT": "Fortinet",
    "SNPS": "Synopsys",
    "CDNS": "Cadence Design Systems",
    "ANSS": "ANSYS",
    "DDOG": "Datadog",
    "NET": "Cloudflare",
    "ZS": "Zscaler",
    "OKTA": "Okta",
    "MDB": "MongoDB",
    "SNOW": "Snowflake",
    "ESTC": "Elastic",
    "CHKP": "Check Point",
    "NTNX": "Nutanix",
    "GTLB": "GitLab",

    # Software - Application
    "CRM": "Salesforce",
    "INTU": "Intuit",
    "SAP": "SAP SE",
    "WDAY": "Workday",
    "ADSK": "Autodesk",
    "TEAM": "Atlassian",
    "NOW": "ServiceNow",
    "HUBS": "HubSpot",
    "DOCU": "DocuSign",
    "ZM": "Zoom Communications",
    "TYL": "Tyler Technologies",
    "PEGA": "Pegasystems",
    "MNDY": "Monday.com",
    "FRSH": "Freshworks",
    "BSY": "Bentley Systems",

    # Information Technology Services
    "IBM": "IBM",
    "ACN": "Accenture",
    "INFY": "Infosys",
    "WIT": "Wipro",
    "CTSH": "Cognizant",
    "DXC": "DXC Technology",
    "EPAM": "EPAM Systems",
    "GLOB": "Globant",
    "IT": "Gartner",

    # Consumer Electronics
    "AAPL": "Apple",
    "SONY": "Sony Group",
    "LPL": "LG Display",

    # Computer Hardware
    "DELL": "Dell Technologies",
    "HPQ": "HP Inc.",
    "HPE": "Hewlett Packard Enterprise",
    "NTAP": "NetApp",
    "PSTG": "Pure Storage",
    "SMCI": "Super Micro Computer",
    "WDC": "Western Digital",
    "STX": "Seagate Technology",

    # Communication Equipment
    "CSCO": "Cisco Systems",
    "ANET": "Arista Networks",
    "MSI": "Motorola Solutions",
    "JNPR": "Juniper Networks",
    "ZBRA": "Zebra Technologies",
    "ERIC": "Ericsson",
    "NOK": "Nokia",
    "AAOI": "Applied Optoelectronics",

    # Electronic Components
    "TEL": "TE Connectivity",
    "APH": "Amphenol",
    "GLW": "Corning",
    "CDW": "CDW Corporation",
    "ARW": "Arrow Electronics",
    "AVT": "Avnet",

    # Scientific & Technical Instruments
    "ROP": "Roper Technologies",
    "KEYS": "Keysight Technologies",
    "TDY": "Teledyne Technologies",
    "TRMB": "Trimble",
    "COHR": "Coherent",

    # AI & Data Specific
    "PLTR": "Palantir Technologies",
    "AI": "C3.ai",
    "BBAI": "BigBear.ai",
    "SOUN": "SoundHound AI",

    # ═══════════════════════════════════════════
    # 8. Basic Materials
    # ═══════════════════════════════════════════
    # Specialty Chemicals
    "LIN": "Linde",
    "SHW": "Sherwin-Williams",
    "APD": "Air Products and Chemicals",
    "ECL": "Ecolab",
    "PPG": "PPG Industries",
    "ALB": "Albemarle",
    "IFF": "International Flavors & Fragrances",
    "RPM": "RPM International",
    "AXTA": "Axalta Coating Systems",
    "AVNT": "Avient",

    # Agricultural Inputs & Fertilizers
    "NTR": "Nutrien",
    "CF": "CF Industries",
    "MOS": "Mosaic",
    "CTVA": "Corteva",
    "FMC": "FMC Corporation",
    "ICL": "ICL Group",
    "SQM": "Sociedad Química y Minera",

    # Steel
    "NUE": "Nucor",
    "STLD": "Steel Dynamics",
    "VALE": "Vale",
    "RIO": "Rio Tinto",
    "BHP": "BHP Group",
    "CLF": "Cleveland-Cliffs",
    "X": "United States Steel",
    "TX": "Ternium",
    "ASTL": "Algoma Steel",

    # Copper & Industrial Metals
    "FCX": "Freeport-McMoRan",
    "SCCO": "Southern Copper",
    "TECK": "Teck Resources",

    # Aluminum
    "AA": "Alcoa",
    "ACH": "Aluminum Corp of China",
    "CENX": "Century Aluminum",

    # Gold Mining
    "NEM": "Newmont",
    "GOLD": "Barrick Gold",
    "AEM": "Agnico Eagle Mines",
    "AU": "AngloGold Ashanti",
    "KGC": "Kinross Gold",
    "WPM": "Wheaton Precious Metals",
    "FNV": "Franco-Nevada",
    "GFI": "Gold Fields",
    "HMY": "Harmony Gold",
    "BTG": "B2Gold",
    "AGI": "Alamos Gold",

    # Silver Mining
    "PAAS": "Pan American Silver",
    "HL": "Hecla Mining",
    "AG": "First Majestic Silver",

    # Other Precious Metals
    "SBSW": "Sibanye Stillwater",
    "SAND": "Sandstorm Gold",

    # Forest Products
    "WY": "Weyerhaeuser",
    "LPX": "Louisiana-Pacific",

    # Building Materials
    "VMC": "Vulcan Materials",
    "MLM": "Martin Marietta Materials",
    "EXP": "Eagle Materials",
    "CRH": "CRH plc",

    # Chemicals - Diversified
    "DOW": "Dow Inc.",
    "DD": "DuPont",
    "LYB": "LyondellBasell",
    "WLK": "Westlake",
    "EMN": "Eastman Chemical",
    "HUN": "Huntsman",
    "CE": "Celanese",
    "ASH": "Ashland",

    # ═══════════════════════════════════════════
    # 9. Utilities
    # ═══════════════════════════════════════════
    # Regulated Electric
    "NEE": "NextEra Energy",
    "SO": "Southern Company",
    "DUK": "Duke Energy",
    "AEP": "American Electric Power",
    "D": "Dominion Energy",
    "XEL": "Xcel Energy",
    "EXC": "Exelon",
    "ED": "Consolidated Edison",
    "PEG": "Public Service Enterprise Group",
    "WEC": "WEC Energy Group",
    "PCG": "PG&E Corporation",
    "DTE": "DTE Energy",
    "AEE": "Ameren",
    "ETR": "Entergy",
    "EIX": "Edison International",
    "ES": "Eversource Energy",
    "FE": "FirstEnergy",
    "PPL": "PPL Corporation",
    "CMS": "CMS Energy",
    "EVRG": "Evergy",
    "LNT": "Alliant Energy",

    # Diversified
    "CEG": "Constellation Energy",
    "VST": "Vistra Corp",
    "TLN": "Talen Energy",
    "NRG": "NRG Energy",
    "ATO": "Atmos Energy",

    # Regulated Gas
    "SRE": "Sempra",
    "NI": "NiSource",
    "CNP": "CenterPoint Energy",

    # Renewable
    "BIP": "Brookfield Infrastructure Partners",
    "ENLT": "Enlight Renewable Energy",
    "OKLO": "Oklo (SMR Nuclear)",

    # Water
    "AWK": "American Water Works",
    "SBS": "Sabesp",

    # Foreign Diversified
    "NGG": "National Grid",
    "FTS": "Fortis",
    "EMA": "Emera",
    "KEP": "Korea Electric Power",
}


# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# Forex Market — 20 Currency Pairs
# ══════════════════════════════════════════════════════════════

FOREX_STOCKS = {
    # ── أزواج رئيسية (Major Pairs) ──
    "EURUSD=X": "يورو / دولار",
    "GBPUSD=X": "جنيه / دولار",
    "USDJPY=X": "دولار / ين",
    "USDCHF=X": "دولار / فرنك",
    "AUDUSD=X": "أسترالي / دولار",
    "USDCAD=X": "دولار / كندي",
    "NZDUSD=X": "نيوزلندي / دولار",
    # ── أزواج تقاطعية (Cross Pairs) ──
    "EURGBP=X": "يورو / جنيه",
    "EURJPY=X": "يورو / ين",
    "GBPJPY=X": "جنيه / ين",
    "AUDJPY=X": "أسترالي / ين",
    "EURAUD=X": "يورو / أسترالي",
    "EURCHF=X": "يورو / فرنك",
    "GBPCHF=X": "جنيه / فرنك",
    "GBPAUD=X": "جنيه / أسترالي",
    "EURCAD=X": "يورو / كندي",
    "AUDCAD=X": "أسترالي / كندي",
    "AUDNZD=X": "أسترالي / نيوزلندي",
    "CADJPY=X": "كندي / ين",
    "CHFJPY=X": "فرنك / ين",
}


# ══════════════════════════════════════════════════════════════
# Crypto Market — Top 10 Cryptocurrencies
# ══════════════════════════════════════════════════════════════

CRYPTO_STOCKS = {
    # ── عملات رقمية كبرى ──
    "BTC-USD": "بيتكوين",
    "ETH-USD": "إيثيريوم",
    "BNB-USD": "بي إن بي",
    "SOL-USD": "سولانا",
    "XRP-USD": "ريبل",
    # ── عملات رقمية بديلة ──
    "ADA-USD": "كاردانو",
    "DOGE-USD": "دوجكوين",
    "AVAX-USD": "أفالانش",
    "DOT-USD": "بولكادوت",
    "LINK-USD": "تشين لينك",
}


# ══════════════════════════════════════════════════════════════
# Commodities — Gold, Silver & Metals
# ══════════════════════════════════════════════════════════════

COMMODITIES_STOCKS = {
    # ── المعادن الثمينة ──
    "GC=F": "الذهب",
    "SI=F": "الفضة",
    "PL=F": "البلاتين",
    "PA=F": "البلاديوم",
    # ── الطاقة ──
    "CL=F": "النفط الخام",
    "BZ=F": "برنت",
    "NG=F": "الغاز الطبيعي",
    # ── المعادن الصناعية ──
    "HG=F": "النحاس",
    "ALI=F": "الألمنيوم",
    # ── الزراعية ──
    "ZC=F": "الذرة",
}


# ══════════════════════════════════════════════════════════════
# Saudi Sector Mapping — Based on Tadawul GICS Classification
# Source: Saudi Exchange official sector indices
# ══════════════════════════════════════════════════════════════

SAUDI_SECTORS = {
    # ══════════════════════════════════════════════════════════
    # الطاقة
    # ══════════════════════════════════════════════════════════
    **{t: "الطاقة" for t in [
        "2030.SR",  # المصافي
        "2222.SR",  # أرامكو السعودية
        "2380.SR",  # بترو رابغ
        "2381.SR",  # الحفر العربية
        "2382.SR",  # أديس
        "4030.SR",  # البحري
    ]},
    # ══════════════════════════════════════════════════════════
    # المواد الأساسية (بتروكيماويات + أسمنت + تعدين)
    # ══════════════════════════════════════════════════════════
    **{t: "المواد الأساسية" for t in [
        "1201.SR",  # تكوين
        "1202.SR",  # مبكو
        "1210.SR",  # بي سي آي
        "1211.SR",  # معادن
        "1301.SR",  # أسلاك
        "1304.SR",  # اليمامة للحديد
        "1320.SR",  # أنابيب السعودية
        "1321.SR",  # أنابيب الشرق
        "1322.SR",  # أماك
        "1323.SR",  # يو سي آي سي
        "1324.SR",  # صالح الراشد
        "2001.SR",  # كيمانول
        "2010.SR",  # سابك
        "2020.SR",  # سابك للمغذيات الزراعية
        "2060.SR",  # التصنيع
        "2090.SR",  # جبسكو
        "2150.SR",  # زجاج
        "2170.SR",  # اللجين
        "2180.SR",  # فيبكو
        "2200.SR",  # أنابيب
        "2210.SR",  # نماء للكيماويات
        "2220.SR",  # معدنية
        "2223.SR",  # لوبريف
        "2240.SR",  # صناعات
        "2250.SR",  # المجموعة السعودية
        "2290.SR",  # ينساب
        "2300.SR",  # صناعة الورق
        "2310.SR",  # سبكيم العالمية
        "2330.SR",  # المتقدمة
        "2350.SR",  # كيان السعودية
        "2360.SR",  # الفخارية
        # الأسمنت
        "3002.SR",  # أسمنت نجران
        "3003.SR",  # أسمنت المدينة
        "3004.SR",  # أسمنت الشمالية
        "3005.SR",  # أسمنت أم القرى
        "3007.SR",  # الواحة
        "3008.SR",  # الكثيري
        "3010.SR",  # أسمنت العربية
        "3020.SR",  # أسمنت اليمامة
        "3030.SR",  # أسمنت السعودية
        "3040.SR",  # أسمنت القصيم
        "3050.SR",  # أسمنت الجنوب
        "3060.SR",  # أسمنت ينبع
        "3080.SR",  # أسمنت الشرقية
        "3090.SR",  # أسمنت تبوك
        "3091.SR",  # أسمنت الجوف
        "3092.SR",  # أسمنت الرياض
        "4143.SR",  # تالكو
    ]},
    # ══════════════════════════════════════════════════════════
    # القطاع الصناعي (سلع رأسمالية + صناعات)
    # ══════════════════════════════════════════════════════════
    **{t: "القطاع الصناعي" for t in [
        "1212.SR",  # أسترا الصناعية
        "1214.SR",  # شاكر
        "1302.SR",  # بوان
        "1303.SR",  # الصناعات الكهربائية
        "2040.SR",  # الخزف السعودي
        "2110.SR",  # الكابلات السعودية
        "2160.SR",  # أميانتيت
        "2320.SR",  # البابطين
        "2370.SR",  # مسك
        "4110.SR",  # باتك
        "4140.SR",  # صادرات
        "4141.SR",  # العمران
        "4142.SR",  # كابلات الرياض
        "4144.SR",  # رؤوم
        "4145.SR",  # أو جي سي
        "4146.SR",  # جاز
        "4147.SR",  # سي جي إس
        "4148.SR",  # الوسائل الصناعية
    ]},
    # ══════════════════════════════════════════════════════════
    # النقل والخدمات اللوجستية
    # ══════════════════════════════════════════════════════════
    **{t: "النقل" for t in [
        "2190.SR",  # سيسكو القابضة
        "4031.SR",  # الخدمات الأرضية
        "4040.SR",  # سابتكو
        "4260.SR",  # بدجت السعودية
        "4261.SR",  # ذيب
        "4262.SR",  # لومي
        "4263.SR",  # سال
        "4264.SR",  # طيران ناس
        "4265.SR",  # شري
    ]},
    # ══════════════════════════════════════════════════════════
    # الخدمات التجارية والمهنية
    # ══════════════════════════════════════════════════════════
    **{t: "الخدمات التجارية" for t in [
        "1831.SR",  # مهارة
        "1832.SR",  # صدر
        "1833.SR",  # الموارد
        "1834.SR",  # سماسكو
        "1835.SR",  # تمكين
        "4270.SR",  # طباعة وتغليف
        "6004.SR",  # كاتريون
    ]},
    # ══════════════════════════════════════════════════════════
    # تجزئة وتوزيع السلع الكمالية
    # ══════════════════════════════════════════════════════════
    **{t: "السلع الكمالية" for t in [
        "4003.SR",  # إكسترا
        "4008.SR",  # ساكو
        "4050.SR",  # ساسكو
        "4051.SR",  # باعظيم
        "4190.SR",  # جرير
        "4191.SR",  # أبو معطي
        "4192.SR",  # السيف غاليري
        "4193.SR",  # نايس ون
        "4194.SR",  # محطة البناء
        "4200.SR",  # الدريس
        "4240.SR",  # سينومي ريتيل
    ]},
    # ══════════════════════════════════════════════════════════
    # السلع طويلة الأجل
    # ══════════════════════════════════════════════════════════
    **{t: "السلع طويلة الأجل" for t in [
        "1213.SR",  # نسيج
        "2130.SR",  # صدق
        "2340.SR",  # ارتيكس
        "4011.SR",  # لازوردي
        "4012.SR",  # الأصيل
        "4180.SR",  # مجموعة فتيحي
    ]},
    # ══════════════════════════════════════════════════════════
    # إنتاج الأغذية
    # ══════════════════════════════════════════════════════════
    **{t: "إنتاج الأغذية" for t in [
        "2050.SR",  # مجموعة صافولا
        "2100.SR",  # وفرة
        "2270.SR",  # سدافكو
        "2280.SR",  # المراعي
        "2281.SR",  # تنمية
        "2282.SR",  # نقي
        "2283.SR",  # المطاحن الأولى
        "2284.SR",  # المطاحن الحديثة
        "2285.SR",  # المطاحن العربية
        "2286.SR",  # المطاحن الرابعة
        "2287.SR",  # إنتاج
        "2288.SR",  # نفوذ
        "4080.SR",  # سناد القابضة
        "6001.SR",  # حلواني إخوان
        "6010.SR",  # نادك
        "6020.SR",  # جاكو
        "6040.SR",  # تبوك الزراعية
        "6050.SR",  # الأسماك
        "6060.SR",  # الشرقية للتنمية
        "6070.SR",  # الجوف
        "6090.SR",  # جازادكو
    ]},
    # ══════════════════════════════════════════════════════════
    # الرعاية الصحية
    # ══════════════════════════════════════════════════════════
    **{t: "الرعاية الصحية" for t in [
        "2140.SR",  # أيان
        "2230.SR",  # الكيميائية
        "4002.SR",  # المواساة
        "4004.SR",  # دله الصحية
        "4005.SR",  # رعاية
        "4007.SR",  # الحمادي
        "4009.SR",  # السعودي الألماني الصحية
        "4013.SR",  # سليمان الحبيب
        "4014.SR",  # دار المعدات
        "4017.SR",  # فقيه الطبية
        "4018.SR",  # الموسى
        "4019.SR",  # اس ام سي للرعاية الصحية
        "4021.SR",  # المركز الكندي الطبي
    ]},
    # ══════════════════════════════════════════════════════════
    # الأدوية
    # ══════════════════════════════════════════════════════════
    **{t: "الأدوية" for t in [
        "2070.SR",  # الدوائية
        "4015.SR",  # جمجوم فارما
        "4016.SR",  # أفالون فارما
    ]},
    # ══════════════════════════════════════════════════════════
    # البنوك
    # ══════════════════════════════════════════════════════════
    **{t: "البنوك" for t in [
        "1010.SR",  # الرياض
        "1020.SR",  # الجزيرة
        "1030.SR",  # الاستثمار
        "1050.SR",  # بي اس اف
        "1060.SR",  # الأول
        "1080.SR",  # العربي
        "1120.SR",  # الراجحي
        "1140.SR",  # البلاد
        "1150.SR",  # الإنماء
        "1180.SR",  # الأهلي
    ]},
    # ══════════════════════════════════════════════════════════
    # الاستثمار والتمويل (الخدمات المالية)
    # ══════════════════════════════════════════════════════════
    **{t: "الخدمات المالية" for t in [
        "1111.SR",  # مجموعة تداول
        "1182.SR",  # أملاك
        "1183.SR",  # سهل
        "2120.SR",  # متطورة
        "4081.SR",  # النايفات
        "4082.SR",  # مرنة
        "4083.SR",  # تسهيل
        "4084.SR",  # دراية
        "4130.SR",  # درب السعودية
        "4280.SR",  # المملكة
    ]},
    # ══════════════════════════════════════════════════════════
    # التأمين
    # ══════════════════════════════════════════════════════════
    **{t: "التأمين" for t in [
        "8010.SR",  # التعاونية
        "8012.SR",  # جزيرة تكافل
        "8020.SR",  # ملاذ للتأمين
        "8030.SR",  # ميدغلف للتأمين
        "8040.SR",  # متكاملة
        "8050.SR",  # سلامة
        "8060.SR",  # ولاء
        "8070.SR",  # الدرع العربي
        "8100.SR",  # سايكو
        "8120.SR",  # اتحاد الخليج الأهلية
        "8150.SR",  # أسيج
        "8160.SR",  # التأمين العربية
        "8170.SR",  # الاتحاد
        "8180.SR",  # الصقر للتأمين
        "8190.SR",  # المتحدة للتأمين
        "8200.SR",  # الإعادة السعودية
        "8210.SR",  # بوبا العربية
        "8230.SR",  # تكافل الراجحي
        "8240.SR",  # تشب
        "8250.SR",  # جي آي جي
        "8260.SR",  # الخليجية العامة
        "8280.SR",  # ليفا
        "8300.SR",  # الوطنية
        "8310.SR",  # أمانة للتأمين
        "8311.SR",  # عناية
        "8313.SR",  # رسن
    ]},
    # ══════════════════════════════════════════════════════════
    # الاتصالات
    # ══════════════════════════════════════════════════════════
    **{t: "الاتصالات" for t in [
        "7010.SR",  # اس تي سي
        "7020.SR",  # إتحاد إتصالات
        "7030.SR",  # زين السعودية
        "7040.SR",  # قو للإتصالات
    ]},
    # ══════════════════════════════════════════════════════════
    # المرافق العامة
    # ══════════════════════════════════════════════════════════
    **{t: "المرافق العامة" for t in [
        "2080.SR",  # الغاز
        "2081.SR",  # الخريف
        "2082.SR",  # أكوا
        "2083.SR",  # مرافق
        "2084.SR",  # مياهنا
        "5110.SR",  # السعودية للطاقة
    ]},
    # ══════════════════════════════════════════════════════════
    # العقارات
    # ══════════════════════════════════════════════════════════
    **{t: "العقارات" for t in [
        "4020.SR",  # العقارية
        "4090.SR",  # طيبة
        "4100.SR",  # مكة
        "4150.SR",  # التعمير
        "4220.SR",  # إعمار
        "4230.SR",  # البحر الأحمر
        "4250.SR",  # جبل عمر
        "4300.SR",  # دار الأركان
        "4310.SR",  # مدينة المعرفة
        "4320.SR",  # الأندلس
        "4321.SR",  # سينومي سنترز
        "4322.SR",  # رتال
        "4323.SR",  # سمو
        "4324.SR",  # بنان
        "4325.SR",  # مسار
        "4326.SR",  # الماجدية
        "4327.SR",  # الرمز
    ]},
    # ══════════════════════════════════════════════════════════
    # التقنية
    # ══════════════════════════════════════════════════════════
    **{t: "التقنية" for t in [
        "7200.SR",  # ام آي اس
        "7201.SR",  # بحر العرب
        "7202.SR",  # سلوشنز
        "7203.SR",  # علم
        "7204.SR",  # توبي
        "7211.SR",  # عزم
    ]},
    # ══════════════════════════════════════════════════════════
    # الخدمات الاستهلاكية
    # ══════════════════════════════════════════════════════════
    **{t: "الخدمات الاستهلاكية" for t in [
        "1810.SR",  # سيرا
        "1820.SR",  # بان
        "1830.SR",  # لجام للرياضة
        "4170.SR",  # شمس
        "4290.SR",  # الخليج للتدريب
        "4291.SR",  # الوطنية للتعليم
        "4292.SR",  # عطاء
        "6002.SR",  # هرفي للأغذية
        "6012.SR",  # ريدان
        "6013.SR",  # التطويرية الغذائية
        "6014.SR",  # الآمار
        "6015.SR",  # أمريكانا
        "6016.SR",  # برغرايززر
        "6017.SR",  # جاهز
        "6018.SR",  # الأندية للرياضة
        "6019.SR",  # المسار الشامل
    ]},
    # ══════════════════════════════════════════════════════════
    # الإعلام والترفيه
    # ══════════════════════════════════════════════════════════
    **{t: "الإعلام والترفيه" for t in [
        "4070.SR",  # تهامة
        "4071.SR",  # العربية
        "4072.SR",  # مجموعة إم بي سي
        "4210.SR",  # الأبحاث والإعلام
    ]},
    # ══════════════════════════════════════════════════════════
    # المنتجات المنزلية والشخصية
    # ══════════════════════════════════════════════════════════
    **{t: "المنتجات المنزلية والشخصية" for t in [
        "4165.SR",  # الماجد للعود
    ]},
    # ══════════════════════════════════════════════════════════
    # تجزئة وتوزيع السلع الاستهلاكية
    # ══════════════════════════════════════════════════════════
    **{t: "تجزئة السلع الاستهلاكية" for t in [
        "4001.SR",  # أسواق العثيم
        "4006.SR",  # أسواق المزرعة
        "4061.SR",  # أنعام القابضة
        "4160.SR",  # ثمار
        "4161.SR",  # بن داود
        "4162.SR",  # المنجم
        "4163.SR",  # الدواء
        "4164.SR",  # النهدي
    ]},
    # ══════════════════════════════════════════════════════════
}



# US Sector Mapping (top-level)
# ══════════════════════════════════════════════════════════════

US_SECTORS = {
    # Communication Services
    **{t: "خدمات الاتصالات" for t in [
        "GOOG", "GOOGL", "META", "BIDU", "NTES", "RDDT",
        "NFLX", "DIS", "SPOT", "ROKU", "WBD",
        "EA", "TTWO", "RBLX",
        "LYV", "TKO", "WMG", "FWONA", "FWONK",
        "TMUS", "VZ", "T",
        "AMX", "VOD", "CHT", "BCE", "RCI", "TU", "TLK", "VIV", "TIGO",
        "CMCSA", "CHTR", "FOX", "FOXA",
        "NWSA", "NWS",
        "APP", "OMC",
        "SATS",
    ]},

    # Consumer Defensive
    **{t: "السلع الاستهلاكية الأساسية" for t in [
        "WMT", "COST", "TGT", "DG", "DLTR", "BJ",
        "KR", "ACI", "SFM", "CASY",
        "KO", "PEP", "MNST", "KDP", "CELH", "CCEP",
        "MDLZ", "GIS", "K", "CPB", "MKC", "SJM", "BG", "ADM", "CALM", "BYND",
        "PG", "UL", "CL", "KMB", "CHD", "CLX", "EL",
        "HSY", "TR",
        "AGRO", "ANDE",
    ]},

    # Consumer Discretionary
    **{t: "السلع الكمالية" for t in [
        "AMZN", "BABA", "MELI", "PDD", "EBAY", "ETSY", "CHWY", "W", "CVNA",
        "HD", "LOW", "TJX", "ROST", "BURL", "ULTA", "BBY", "DKS", "AZO", "ORLY",
        "AAP", "TSCO", "FND", "WSM", "RH", "ASO",
        "NKE", "LULU", "DECK", "VFC", "ONON", "BIRK", "CROX", "SKX", "COLM",
        "AEO", "ANF", "URBN", "GAP",
        "LVMUY", "CFRUY", "KER", "CPRI", "TPR",
        "TSLA", "TM", "F", "GM", "HMC", "STLA", "RIVN", "LCID", "LI", "NIO", "XPEV", "BYDDY",
        "APTV", "LEA", "BWA", "ALV", "ALSN", "DAN",
        "AN", "LAD", "PAG", "ABG", "GPI", "KMX",
        "LEG", "WHR", "MHK", "SCS",
        "DHI", "LEN", "NVR", "PHM", "TOL", "KBH", "MTH",
        "PKG", "IP", "BALL", "AMCR", "CCK", "AVY", "SEE",
        "DASH",
    ]},

    # Energy
    **{t: "الطاقة" for t in [
        "XOM", "CVX", "SHEL", "BP", "TTE", "EQNR", "E", "PBR", "PBR.A", "EC",
        "SU", "IMO", "CNQ", "CVE",
        "COP", "EOG", "OXY", "CTRA", "DVN", "HES", "MRO", "PXD", "FANG", "APA",
        "CHRD", "MTDR", "AR", "SM", "CRC", "CRGY", "VET", "TPL",
        "ENB", "ET", "EPD", "KMI", "WMB", "OKE", "TRP", "LNG", "MPLX", "WES",
        "PAA", "PAGP", "TRGP", "AROC",
        "MPC", "PSX", "VLO", "DINO", "PBF",
        "SLB", "BKR", "HAL", "TS", "WFRD", "CHX", "LBRT", "NOV", "FTI", "ACDC", "CLB",
        "RIG", "VAL", "NE", "BORR", "HP", "PTEN", "NBR",
        "BTU", "ARLP", "AMR", "HCC", "CEIX", "METC",
        "CCJ", "UEC", "DNN", "URG", "LEU", "BWXT",
        "BEPC", "BEP", "FSLR", "ENPH", "SEDG", "RUN", "NOVA", "ARRY", "SHLS", "CWEN",
        "JKS", "CSIQ", "DQ", "SOL", "MAXN",
    ]},

    # Healthcare
    **{t: "الرعاية الصحية" for t in [
        "LLY", "JNJ", "NVO", "ABBV", "MRK", "AZN", "PFE", "NVS", "BMY", "GSK", "SNY", "TAK",
        "AMGN", "VRTX", "GILD", "REGN", "BIIB", "MRNA", "BNTX", "ALNY", "ARGX",
        "ABT", "ISRG", "SYK", "MDT", "BSX", "BDX", "EW", "ZBH",
        "DXCM", "PODD", "ALC", "COO",
        "TMO", "DHR", "A", "IQV", "MTD", "WAT", "IDXX", "LH", "DGX",
        "UNH", "ELV", "CI", "HUM", "CNC",
        "HCA", "THC", "UHS", "DVA",
        "MCK", "COR", "CAH",
        "CVS", "WBA",
        "VEEV",
    ]},

    # Industrials
    **{t: "القطاع الصناعي" for t in [
        "RTX", "BA", "LMT", "GD", "NOC", "LHX", "TDG", "HWM",
        "CAT", "DE", "CMI", "PCAR", "URI",
        "GE", "HON", "MMM", "ITW", "GEV",
        "ETN", "VRT", "PWR", "EMR", "BE",
        "GWW",
        "PH", "TT", "CARR", "FIX",
        "UNP", "CSX", "NSC", "CNI", "CP",
        "UPS", "FDX",
        "WM", "RSG",
        "JCI",
        "CTAS", "RELX",
    ]},

    # Information Technology
    **{t: "التقنية" for t in [
        "NVDA", "AVGO", "TSM", "AMD", "QCOM", "TXN", "ARM", "MU", "ADI", "LRCX",
        "KLAC", "AMAT", "ASML", "MRVL", "MCHP", "ON", "NXPI", "ASX", "UMC", "ALAB",
        "MSFT", "ORCL", "ADBE", "PANW", "CRWD", "FTNT", "SNPS", "CDNS", "ANSS",
        "DDOG", "NET", "ZS", "OKTA", "MDB", "SNOW", "ESTC", "CHKP", "NTNX", "GTLB",
        "CRM", "INTU", "SAP", "WDAY", "ADSK", "TEAM", "NOW", "HUBS", "DOCU", "ZM",
        "TYL", "PEGA", "MNDY", "FRSH", "BSY",
        "IBM", "ACN", "INFY", "WIT", "CTSH", "DXC", "EPAM", "GLOB", "IT",
        "AAPL", "SONY", "LPL",
        "DELL", "HPQ", "HPE", "NTAP", "PSTG", "SMCI", "WDC", "STX",
        "CSCO", "ANET", "MSI", "JNPR", "ZBRA", "ERIC", "NOK", "AAOI",
        "TEL", "APH", "GLW", "CDW", "ARW", "AVT",
        "ROP", "KEYS", "TDY", "TRMB", "COHR",
        "PLTR", "AI", "BBAI", "SOUN",
    ]},

    # Basic Materials
    **{t: "المواد الأساسية" for t in [
        "LIN", "SHW", "APD", "ECL", "PPG", "ALB", "IFF", "RPM", "AXTA", "AVNT",
        "NTR", "CF", "MOS", "CTVA", "FMC", "ICL", "SQM",
        "NUE", "STLD", "VALE", "RIO", "BHP", "CLF", "X", "TX", "ASTL",
        "FCX", "SCCO", "TECK",
        "AA", "ACH", "CENX",
        "NEM", "GOLD", "AEM", "AU", "KGC", "WPM", "FNV", "GFI", "HMY", "BTG", "AGI",
        "PAAS", "HL", "AG",
        "SBSW", "SAND",
        "WY", "LPX",
        "VMC", "MLM", "EXP", "CRH",
        "DOW", "DD", "LYB", "WLK", "EMN", "HUN", "CE", "ASH",
    ]},

    # Utilities
    **{t: "المرافق العامة" for t in [
        "NEE", "SO", "DUK", "AEP", "D", "XEL", "EXC", "ED", "PEG", "WEC", "PCG",
        "DTE", "AEE", "ETR", "EIX", "ES", "FE", "PPL", "CMS", "EVRG", "LNT",
        "CEG", "VST", "TLN", "NRG", "ATO",
        "SRE", "NI", "CNP",
        "BIP", "ENLT", "OKLO",
        "AWK", "SBS",
        "NGG", "FTS", "EMA", "KEP",
    ]},
}


# ══════════════════════════════════════════════════════════════
# US Industries (sub-sectors) — NEW: granular industry mapping
# ══════════════════════════════════════════════════════════════

US_INDUSTRIES = {
    # ── Communication Services ──
    **{t: "محتوى الإنترنت" for t in ["GOOG", "GOOGL", "META", "BIDU", "NTES", "RDDT"]},
    **{t: "ترفيه - بث ومحتوى" for t in ["NFLX", "DIS", "SPOT", "ROKU", "WBD"]},
    **{t: "ترفيه - ألعاب" for t in ["EA", "TTWO", "RBLX"]},
    **{t: "ترفيه - فعاليات حية وموسيقى" for t in ["LYV", "TKO", "WMG", "FWONA", "FWONK"]},
    **{t: "اتصالات أمريكية" for t in ["TMUS", "VZ", "T"]},
    **{t: "اتصالات دولية" for t in ["AMX", "VOD", "CHT", "BCE", "RCI", "TU", "TLK", "VIV", "TIGO"]},
    **{t: "تلفزيون وبث" for t in ["CMCSA", "CHTR", "FOX", "FOXA"]},
    **{t: "نشر" for t in ["NWSA", "NWS"]},
    **{t: "إعلانات" for t in ["APP", "OMC"]},
    **{t: "أقمار صناعية" for t in ["SATS"]},

    # ── Consumer Defensive ──
    **{t: "تجزئة وتخفيضات" for t in ["WMT", "COST", "TGT", "DG", "DLTR", "BJ"]},
    **{t: "بقالة" for t in ["KR", "ACI", "SFM", "CASY"]},
    **{t: "مشروبات غير كحولية" for t in ["KO", "PEP", "MNST", "KDP", "CELH", "CCEP"]},
    **{t: "أغذية معبأة" for t in ["MDLZ", "GIS", "K", "CPB", "MKC", "SJM", "BG", "ADM", "CALM", "BYND"]},
    **{t: "منتجات منزلية وعناية شخصية" for t in ["PG", "UL", "CL", "KMB", "CHD", "CLX", "EL"]},
    **{t: "حلويات" for t in ["HSY", "TR"]},
    **{t: "منتجات زراعية" for t in ["AGRO", "ANDE"]},

    # ── Consumer Discretionary ──
    **{t: "تجزئة إلكترونية" for t in ["AMZN", "BABA", "MELI", "PDD", "EBAY", "ETSY", "CHWY", "W", "CVNA"]},
    **{t: "تجزئة متخصصة" for t in [
        "HD", "LOW", "TJX", "ROST", "BURL", "ULTA", "BBY", "DKS", "AZO", "ORLY",
        "AAP", "TSCO", "FND", "WSM", "RH", "ASO",
    ]},
    **{t: "ملابس وأحذية - تصنيع" for t in ["NKE", "LULU", "DECK", "VFC", "ONON", "BIRK", "CROX", "SKX", "COLM"]},
    **{t: "ملابس - تجزئة" for t in ["AEO", "ANF", "URBN", "GAP"]},
    **{t: "سلع فاخرة" for t in ["LVMUY", "CFRUY", "KER", "CPRI", "TPR"]},
    **{t: "سيارات" for t in ["TSLA", "TM", "F", "GM", "HMC", "STLA", "RIVN", "LCID", "LI", "NIO", "XPEV", "BYDDY"]},
    **{t: "قطع غيار سيارات" for t in ["APTV", "LEA", "BWA", "ALV", "ALSN", "DAN"]},
    **{t: "وكالات سيارات" for t in ["AN", "LAD", "PAG", "ABG", "GPI", "KMX"]},
    **{t: "أثاث ومنزل" for t in ["LEG", "WHR", "MHK", "SCS"]},
    **{t: "مقاولو بناء" for t in ["DHI", "LEN", "NVR", "PHM", "TOL", "KBH", "MTH"]},
    **{t: "تغليف" for t in ["PKG", "IP", "BALL", "AMCR", "CCK", "AVY", "SEE"]},
    **{t: "مطاعم وتوصيل" for t in ["DASH"]},

    # ── Energy ──
    **{t: "نفط وغاز متكامل" for t in [
        "XOM", "CVX", "SHEL", "BP", "TTE", "EQNR", "E", "PBR", "PBR.A", "EC",
        "SU", "IMO", "CNQ", "CVE",
    ]},
    **{t: "استكشاف وإنتاج نفط" for t in [
        "COP", "EOG", "OXY", "CTRA", "DVN", "HES", "MRO", "PXD", "FANG", "APA",
        "CHRD", "MTDR", "AR", "SM", "CRC", "CRGY", "VET", "TPL",
    ]},
    **{t: "نقل وتخزين نفط" for t in [
        "ENB", "ET", "EPD", "KMI", "WMB", "OKE", "TRP", "LNG", "MPLX", "WES",
        "PAA", "PAGP", "TRGP", "AROC",
    ]},
    **{t: "تكرير وتسويق نفط" for t in ["MPC", "PSX", "VLO", "DINO", "PBF"]},
    **{t: "خدمات حفر ومعدات" for t in [
        "SLB", "BKR", "HAL", "TS", "WFRD", "CHX", "LBRT", "NOV", "FTI", "ACDC", "CLB",
    ]},
    **{t: "حفر آبار" for t in ["RIG", "VAL", "NE", "BORR", "HP", "PTEN", "NBR"]},
    **{t: "فحم حراري" for t in ["BTU", "ARLP", "AMR", "HCC", "CEIX", "METC"]},
    **{t: "يورانيوم ووقود نووي" for t in ["CCJ", "UEC", "DNN", "URG", "LEU", "BWXT"]},
    **{t: "طاقة متجددة" for t in [
        "BEPC", "BEP", "FSLR", "ENPH", "SEDG", "RUN", "NOVA", "ARRY", "SHLS", "CWEN",
    ]},
    **{t: "تصنيع طاقة شمسية" for t in ["JKS", "CSIQ", "DQ", "SOL", "MAXN"]},

    # ── Healthcare ──
    **{t: "أدوية كبرى" for t in [
        "LLY", "JNJ", "NVO", "ABBV", "MRK", "AZN", "PFE", "NVS", "BMY", "GSK", "SNY", "TAK",
    ]},
    **{t: "تقنية حيوية" for t in [
        "AMGN", "VRTX", "GILD", "REGN", "BIIB", "MRNA", "BNTX", "ALNY", "ARGX",
    ]},
    **{t: "أجهزة طبية" for t in ["ABT", "ISRG", "SYK", "MDT", "BSX", "BDX", "EW", "ZBH"]},
    **{t: "مستلزمات طبية" for t in ["DXCM", "PODD", "ALC", "COO"]},
    **{t: "تشخيص وأبحاث" for t in [
        "TMO", "DHR", "A", "IQV", "MTD", "WAT", "IDXX", "LH", "DGX",
    ]},
    **{t: "تأمين صحي" for t in ["UNH", "ELV", "CI", "HUM", "CNC"]},
    **{t: "مستشفيات ومرافق" for t in ["HCA", "THC", "UHS", "DVA"]},
    **{t: "توزيع طبي" for t in ["MCK", "COR", "CAH"]},
    **{t: "صيدليات تجزئة" for t in ["CVS", "WBA"]},
    **{t: "خدمات معلومات صحية" for t in ["VEEV"]},

    # ── Industrials ──
    **{t: "طيران ودفاع" for t in ["RTX", "BA", "LMT", "GD", "NOC", "LHX", "TDG", "HWM"]},
    **{t: "معدات ثقيلة" for t in ["CAT", "DE", "CMI", "PCAR", "URI"]},
    **{t: "تكتلات صناعية" for t in ["GE", "HON", "MMM", "ITW", "GEV"]},
    **{t: "معدات كهربائية وطاقة" for t in ["ETN", "VRT", "PWR", "EMR", "BE"]},
    **{t: "توزيع صناعي" for t in ["GWW"]},
    **{t: "آلات صناعية متخصصة" for t in ["PH", "TT", "CARR", "FIX"]},
    **{t: "سكك حديدية" for t in ["UNP", "CSX", "NSC", "CNI", "CP"]},
    **{t: "شحن ولوجستيات" for t in ["UPS", "FDX"]},
    **{t: "إدارة النفايات" for t in ["WM", "RSG"]},
    **{t: "منتجات بناء" for t in ["JCI"]},
    **{t: "خدمات أعمال" for t in ["CTAS", "RELX"]},

    # ── Information Technology ──
    **{t: "أشباه موصلات" for t in [
        "NVDA", "AVGO", "TSM", "AMD", "QCOM", "TXN", "ARM", "MU", "ADI", "LRCX",
        "KLAC", "AMAT", "ASML", "MRVL", "MCHP", "ON", "NXPI", "ASX", "UMC", "ALAB",
    ]},
    **{t: "برمجيات بنية تحتية" for t in [
        "MSFT", "ORCL", "ADBE", "PANW", "CRWD", "FTNT", "SNPS", "CDNS", "ANSS",
        "DDOG", "NET", "ZS", "OKTA", "MDB", "SNOW", "ESTC", "CHKP", "NTNX", "GTLB",
    ]},
    **{t: "برمجيات تطبيقية" for t in [
        "CRM", "INTU", "SAP", "WDAY", "ADSK", "TEAM", "NOW", "HUBS", "DOCU", "ZM",
        "TYL", "PEGA", "MNDY", "FRSH", "BSY",
    ]},
    **{t: "خدمات تقنية" for t in [
        "IBM", "ACN", "INFY", "WIT", "CTSH", "DXC", "EPAM", "GLOB", "IT",
    ]},
    **{t: "إلكترونيات استهلاكية" for t in ["AAPL", "SONY", "LPL"]},
    **{t: "أجهزة حاسوب" for t in ["DELL", "HPQ", "HPE", "NTAP", "PSTG", "SMCI", "WDC", "STX"]},
    **{t: "معدات اتصالات" for t in ["CSCO", "ANET", "MSI", "JNPR", "ZBRA", "ERIC", "NOK", "AAOI"]},
    **{t: "مكونات إلكترونية" for t in ["TEL", "APH", "GLW", "CDW", "ARW", "AVT"]},
    **{t: "أدوات علمية" for t in ["ROP", "KEYS", "TDY", "TRMB", "COHR"]},
    **{t: "ذكاء اصطناعي" for t in ["PLTR", "AI", "BBAI", "SOUN"]},

    # ── Basic Materials ──
    **{t: "كيماويات متخصصة" for t in [
        "LIN", "SHW", "APD", "ECL", "PPG", "ALB", "IFF", "RPM", "AXTA", "AVNT",
    ]},
    **{t: "مدخلات زراعية وأسمدة" for t in ["NTR", "CF", "MOS", "CTVA", "FMC", "ICL", "SQM"]},
    **{t: "حديد وصلب" for t in ["NUE", "STLD", "VALE", "RIO", "BHP", "CLF", "X", "TX", "ASTL"]},
    **{t: "نحاس ومعادن صناعية" for t in ["FCX", "SCCO", "TECK"]},
    **{t: "ألمنيوم" for t in ["AA", "ACH", "CENX"]},
    **{t: "تعدين ذهب" for t in [
        "NEM", "GOLD", "AEM", "AU", "KGC", "WPM", "FNV", "GFI", "HMY", "BTG", "AGI",
    ]},
    **{t: "تعدين فضة" for t in ["PAAS", "HL", "AG"]},
    **{t: "معادن نفيسة أخرى" for t in ["SBSW", "SAND"]},
    **{t: "منتجات الغابات" for t in ["WY", "LPX"]},
    **{t: "مواد بناء" for t in ["VMC", "MLM", "EXP", "CRH"]},
    **{t: "كيماويات متنوعة" for t in ["DOW", "DD", "LYB", "WLK", "EMN", "HUN", "CE", "ASH"]},

    # ── Utilities ──
    **{t: "كهرباء منظمة" for t in [
        "NEE", "SO", "DUK", "AEP", "D", "XEL", "EXC", "ED", "PEG", "WEC", "PCG",
        "DTE", "AEE", "ETR", "EIX", "ES", "FE", "PPL", "CMS", "EVRG", "LNT",
    ]},
    **{t: "مرافق متنوعة" for t in ["CEG", "VST", "TLN", "NRG", "ATO"]},
    **{t: "غاز منظم" for t in ["SRE", "NI", "CNP"]},
    **{t: "مرافق متجددة" for t in ["BIP", "ENLT", "OKLO"]},
    **{t: "مياه" for t in ["AWK", "SBS"]},
    **{t: "مرافق دولية" for t in ["NGG", "FTS", "EMA", "KEP"]},
}

# Sector mapping for Forex pairs
FOREX_SECTORS = {
    # أزواج رئيسية (Major Pairs — contain USD)
    **{t: "أزواج رئيسية" for t in [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
        "AUDUSD=X", "USDCAD=X", "NZDUSD=X",
    ]},
    # أزواج تقاطعية (Cross Pairs — no USD)
    **{t: "أزواج تقاطعية" for t in [
        "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X",
        "EURAUD=X", "EURCHF=X", "GBPCHF=X", "GBPAUD=X",
        "EURCAD=X", "AUDCAD=X", "AUDNZD=X", "CADJPY=X", "CHFJPY=X",
    ]},
}


# Sector mapping for Crypto
CRYPTO_SECTORS = {
    # عملات رقمية كبرى (Large Cap)
    **{t: "عملات رقمية كبرى" for t in [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
    ]},
    # عملات رقمية بديلة (Altcoins)
    **{t: "عملات رقمية بديلة" for t in [
        "ADA-USD", "DOGE-USD", "AVAX-USD", "DOT-USD", "LINK-USD",
    ]},
}


# Sector mapping for Commodities
COMMODITIES_SECTORS = {
    **{t: "معادن ثمينة" for t in [
        "GC=F", "SI=F", "PL=F", "PA=F",
    ]},
    **{t: "طاقة" for t in [
        "CL=F", "BZ=F", "NG=F",
    ]},
    **{t: "معادن صناعية" for t in [
        "HG=F", "ALI=F",
    ]},
    **{t: "سلع زراعية" for t in [
        "ZC=F",
    ]},
}


# ══════════════════════════════════════════════════════════════
# MARKET CONFIGS
# ══════════════════════════════════════════════════════════════

MARKETS = {
    "🇸🇦 السوق السعودي (TASI)": {
        "key": "saudi",
        "stocks": SAUDI_STOCKS,
        "label": "السوق السعودي",
    },
    "🇺🇸 السوق الأمريكي (S&P 500)": {
        "key": "us",
        "stocks": US_STOCKS,
        "label": "السوق الأمريكي",
    },
    "💱 الفوركس (Forex)": {
        "key": "forex",
        "stocks": FOREX_STOCKS,
        "label": "الفوركس",
    },
    "₿ العملات الرقمية (Crypto)": {
        "key": "crypto",
        "stocks": CRYPTO_STOCKS,
        "label": "العملات الرقمية",
    },
    "🥇 السلع (Commodities)": {
        "key": "commodities",
        "stocks": COMMODITIES_STOCKS,
        "label": "السلع",
    },
}


def get_all_tickers(market: str = "saudi") -> list:
    """Get all tickers for a market."""
    if market == "us":
        return list(US_STOCKS.keys())
    if market == "forex":
        return list(FOREX_STOCKS.keys())
    if market == "crypto":
        return list(CRYPTO_STOCKS.keys())
    if market == "commodities":
        return list(COMMODITIES_STOCKS.keys())
    return list(SAUDI_STOCKS.keys())


def get_stock_name(ticker: str) -> str:
    """Get company name for a ticker."""
    for d in (SAUDI_STOCKS, US_STOCKS, FOREX_STOCKS, CRYPTO_STOCKS, COMMODITIES_STOCKS):
        if ticker in d:
            return d[ticker]
    return ticker.replace(".SR", "").replace("=X", "").replace("=F", "").replace("-USD", "")


def get_sector(ticker: str) -> str:
    """Get top-level sector for a ticker."""
    for d in (SAUDI_SECTORS, US_SECTORS, FOREX_SECTORS, CRYPTO_SECTORS, COMMODITIES_SECTORS):
        if ticker in d:
            return d[ticker]
    return "أخرى"


def get_industry(ticker: str) -> str:
    """Get industry (sub-sector) for a ticker. Currently US only."""
    if ticker in US_INDUSTRIES:
        return US_INDUSTRIES[ticker]
    # For non-US, fall back to sector
    return get_sector(ticker)

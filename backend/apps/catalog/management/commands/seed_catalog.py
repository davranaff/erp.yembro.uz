"""
python manage.py seed_catalog [--reset]

Заполняет БД богатым редакторским контентом для каталога yembro.uz.
Тексты пишутся как от лица фермерского бренда: с конкретикой, цифрами и
характером — без канцелярита. Работает на 3 языках (ru / uz-latin / en).
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import (
    Brand,
    CatalogPage,
    Category,
    ContactRequest,
    Direction,
    Product,
    ProductSpec,
)


def _tri(ru: str, uz: str, en: str) -> dict[str, str]:
    return {"ru": ru, "uz": uz, "en": en}


def _set_i18n(obj, field: str, vals: dict[str, str]) -> None:
    for lng, val in vals.items():
        setattr(obj, f"{field}_{lng}", val)


# ── Бренды ──────────────────────────────────────────────────────────────────
BRANDS = [
    {
        "code": "yembro",
        "names": _tri("Yembro", "Yembro", "Yembro"),
        "desc": _tri(
            "Yembro — флагманская линейка комбикормов, рождённая прямо на ферме. Не в маркетинговом отделе, а в кормовом цеху, где зоотехник пробует на ладони каждую партию перед отгрузкой. Полнорационные программы для бройлера, несушки и родительского стада, рассчитанные под линии Cobb 500, Ross 308, Hy-Line и Lohmann. Стабильная рецептура, в которой не «играют» составом ради экономии — потому что мы кормим этим кормом и собственное поголовье.",
            "Yembro — toʻgʻridan-toʻgʻri fermada tugʻilgan flagman yem liniyasi. Marketing boʻlimi emas, balki yem sexida — har bir partiyani ortishdan oldin zootexnik kaftida tekshirib koʻradigan joyda. Cobb 500, Ross 308, Hy-Line va Lohmann liniyalari uchun broyler, tuxum tovuqlari va ota-ona podasiga moʻljallangan toʻliq ratsionli dasturlar. Tejash uchun tarkibi bilan «oʻyin oʻynamaydigan» barqaror retsept — chunki biz ham oʻz podamizni shu yem bilan boqamiz.",
            "Yembro is the flagship feed line, born inside the barn — not in a marketing brief. Our nutritionist tastes every batch by hand before it leaves the mill. Complete programs for broiler, layer and parent stock, calibrated to Cobb 500, Ross 308, Hy-Line and Lohmann genetics. Stable recipes that don't get «trimmed» to save a cent — because we feed our own birds with the same bag.",
        ),
        "meta_title": _tri(
            "Yembro — комбикорма для птицеводства, проверенные собственной фермой",
            "Yembro — oʻz fermamizda sinovdan oʻtgan parranda yemlari",
            "Yembro — poultry feed proven on our own farm",
        ),
        "meta_desc": _tri(
            "Yembro — флагманские полнорационные корма для бройлера, несушки и родительского стада. Cobb / Ross / Hy-Line / Lohmann. Лабораторный QC, доставка по Узбекистану.",
            "Yembro — broyler, tuxum tovuqlari va ota-ona podasi uchun flagman toʻliq ratsionli yemlar. Cobb / Ross / Hy-Line / Lohmann. Laboratoriya QC, Oʻzbekiston boʻylab yetkazib berish.",
            "Yembro — flagship complete feeds for broiler, layer and parent stock. Cobb / Ross / Hy-Line / Lohmann. Lab-checked, delivered across Uzbekistan.",
        ),
        "sort_order": 0,
    },
    {
        "code": "yembro-pro",
        "names": _tri("Yembro Pro", "Yembro Pro", "Yembro Pro"),
        "desc": _tri(
            "Pro — это когда счёт идёт уже не на копейки, а на сотые доли FCR. Усиленный аминокислотный профиль, повышенная энергетическая плотность, точечная балансировка лизин-метионин-треонин. Эта линейка для крупных промышленных фабрик, где каждая партия рождает таблицу — и каждая ошибка корма видна на дашборде уже через две недели. Сделано для тех, кто читает свои показатели по понедельникам и не прощает себе среднюю цифру.",
            "Pro — bu hisob endi tiyinlarda emas, FCR yuzdan bir ulushida boshlanadigan paydo. Kuchaytirilgan aminokislota tarkibi, oshirilgan energiya zichligi, lizin-metionin-treonin nuqtali balansi. Bu liniya yirik sanoat fabrikalari uchun — har bir partiya jadval tugʻdiradigan, yemdagi har bir xato ikki haftadan soʻng dashbordda koʻrinadigan joylar uchun. Dushanba kunlari oʻz koʻrsatkichlarini oʻqiydigan va oʻrtacha raqamga rozi boʻlmaydiganlar uchun yaratilgan.",
            "Pro is for the people who don't count kopecks — they count hundredths of FCR. Reinforced amino acids, denser energy, surgical lysine-methionine-threonine balance. Built for industrial farms where every flock turns into a spreadsheet, and every feed mistake shows up on a dashboard two weeks later. Made for the operators who read their numbers on Monday morning and refuse to settle for «average».",
        ),
        "meta_title": _tri(
            "Yembro Pro — премиум корма для интенсивного птицеводства",
            "Yembro Pro — intensiv parrandachilik uchun premium yemlar",
            "Yembro Pro — premium feeds for intensive poultry",
        ),
        "meta_desc": _tri(
            "Yembro Pro: высокая плотность энергии, расширенные аминокислоты, целевые привесы +5–8%. Для бройлеров и несушек на промышленных фабриках.",
            "Yembro Pro: yuqori energiya zichligi, kengaytirilgan aminokislotalar, vazn ortishi +5–8%. Sanoat fabrikalari uchun broyler va tovuq.",
            "Yembro Pro: dense energy, extended amino acids, +5–8% growth target. Industrial-grade broiler and layer feeds.",
        ),
        "sort_order": 1,
    },
    {
        "code": "yembro-bio",
        "names": _tri("Yembro Bio", "Yembro Bio", "Yembro Bio"),
        "desc": _tri(
            "Bio — это корм для тех ферм, на чьих этикетках написано «без антибиотиков», и которым этот текст не приходится нервно прятать от лаборатории. Никаких АБ, никаких кокцидиостатиков. Вместо них — масло орегано, тимьян, защищённая бутировая кислота, дрожжевые стенки и пробиотики Bacillus. Стенки кишечника держим чистыми по-старому: ароматами, кислотами и хорошей микрофлорой. Линейка для премиум-яйца, экосегмента и фабрик с экспортом.",
            "Bio — bu yorligʻida «antibiotiksiz» deb yozilgan va bu yozuvni laboratoriyadan asablanib yashirishga toʻgʻri kelmaydigan fermalar uchun yem. Antibiotiklar yoʻq, kokkidiostatiklar yoʻq. Ularning oʻrniga — origano moyi, timyan, himoyalangan moy kislotasi, achitqi devorlari va Bacillus probiotiklari. Ichak devorlarini eski usulda toza saqlaymiz: aromatlar, kislotalar va yaxshi mikroflora bilan. Premium tuxum, eko-segment va eksport fabrikalari uchun liniya.",
            "Bio is for the farms whose labels say «no antibiotics» — and who don't have to nervously hide that label from the lab. No antibiotics, no coccidiostats. Instead: oregano oil, thyme, protected butyric acid, yeast walls and Bacillus probiotics. We keep the gut wall clean the old way — with aromas, acids and friendly microbes. Built for premium-egg producers, the eco segment and export-grade operations.",
        ),
        "meta_title": _tri(
            "Yembro Bio — корма без антибиотиков для премиум-сегмента",
            "Yembro Bio — premium-segment uchun antibiotiksiz yemlar",
            "Yembro Bio — antibiotic-free feeds for premium poultry",
        ),
        "meta_desc": _tri(
            "Yembro Bio: ноль антибиотиков, ноль кокцидиостатиков. Фитогеники, органические кислоты, пробиотики. Для эко-яйца и премиум-бройлера.",
            "Yembro Bio: nol antibiotik, nol kokkidiostatik. Fitogeniklar, organik kislotalar, probiotiklar. Eko-tuxum va premium broyler uchun.",
            "Yembro Bio: zero antibiotics, zero coccidiostats. Phytogenics, organic acids, probiotics. For eco-egg and premium broiler.",
        ),
        "sort_order": 2,
    },
]

# ── Категории ──────────────────────────────────────────────────────────────
CATEGORIES = [
    ("broiler", _tri("Бройлер", "Broyler", "Broiler"), Direction.BROILER, None,
        _tri(
            "Программы для мясной птицы линий Cobb 500, Ross 308 и Arbor Acres. Старт-рост-финиш с просчитанным аминокислотным профилем — без перекосов, без «давайте вытянем гроуэром, что недодали в стартере». Каждый этап делает свою работу.",
            "Cobb 500, Ross 308 va Arbor Acres goʻshtli parrandalari uchun dasturlar. Start-oʻsish-yakun — har bir bosqich oʻz vazifasini bajaradigan, aminokislota chetga chiqishlarisiz, «keling, starterda yetishmaganini grouerdan tortib chiqamiz» degan yondashuvsiz.",
            "Programs for meat birds — Cobb 500, Ross 308, Arbor Acres. Starter, grower, finisher with amino acids that line up across stages. No skews, no «let's compensate in grower for what starter missed». Each phase does its own job.",
        )),
    ("layer", _tri("Несушка", "Tuxum tovuqlari", "Layer"), Direction.LAYER, None,
        _tri(
            "Питание промышленной яичной птицы — от первой недели жизни до последнего постпика. Hy-Line, Lohmann, ISA Brown. Кальций ведём по графику — от 1.0% у молодки до 4.2% у пика, по неделям — потому что любой скачок видно на скорлупе.",
            "Sanoat tuxum tovuqlarini boqish — birinchi haftadan oxirgi choʻqqidan keyingi davrgacha. Hy-Line, Lohmann, ISA Brown. Kaltsiyni jadval boʻyicha olib boramiz — yosh tovuqdagi 1.0% dan choʻqqidagi 4.2% gacha, hafta-hafta. Chunki har qanday sakrash poʻchoqda koʻrinadi.",
            "Industrial layer nutrition — from week one to post-peak. Hy-Line, Lohmann, ISA Brown. We walk calcium up by the week — from 1.0% in pullets to 4.2% at peak. Because any spike shows up in shell quality.",
        )),
    ("parent", _tri("Родительское стадо", "Ota-ona podasi", "Parent stock"), Direction.PARENT, None,
        _tri(
            "Корм для родителей — это всегда баланс между «вырастить» и «сохранить». Контролируемый рост ремонтного молодняка, поддержка репродуктивной системы, упор на качество инкубационного яйца. Витамины E, A, D3 в работающих, а не «формальных» дозировках.",
            "Ota-onalar uchun yem — bu doim «oʻstirish» va «saqlash» orasidagi balans. Yoshlarni nazoratli oʻsishi, reproduktiv tizimni qoʻllab-quvvatlash, inkubatsiya tuxumi sifatiga ahamiyat. E, A, D3 vitaminlari «rasmiy» emas, balki ishlaydigan dozalarda.",
            "Parent-stock nutrition is always a balance between «grow» and «preserve». Controlled rearing growth, reproductive support, real focus on hatching-egg quality. Vitamins E, A and D3 dosed to work — not just to tick a box.",
        )),
    ("premix", _tri("Премиксы", "Premikslar", "Premixes"), Direction.UNIVERSAL, None,
        _tri(
            "Витаминно-минеральные концентраты для тех, кто варит корм у себя. Уровни ввода 0.5%, 1% и 2.5%. Полный набор витаминов, микроэлементы в хелатной и неорганической формах, фитаза, холин — всё, что в большом замесе должно быть, и ничего лишнего.",
            "Yemni oʻzi tayyorlaydiganlar uchun vitamin-mineral konsentratlari. Kirish darajalari 0.5%, 1% va 2.5%. Toʻliq vitamin tarkibi, xelat va noorganik shakllarda mikroelementlar, fitaza, xolin — katta zamesda boʻlishi kerak boʻlgan barcha narsalar va keraksiz hech narsa yoʻq.",
            "Vitamin-mineral concentrates for operators who mix their own. Inclusion at 0.5%, 1% or 2.5%. Full vitamin profile, trace minerals in chelated and inorganic forms, phytase, choline — everything a big batch needs, nothing it doesn't.",
        )),
    ("broiler-start", _tri("Старт (бройлер)", "Boshlanish (broyler)", "Starter (broiler)"), Direction.BROILER, "broiler",
        _tri(
            "0–10 дней. На этом этапе мы либо закладываем фундамент, либо догоняем оставшиеся 35 дней. Высокий протеин, выверенный лизин и метионин, гранула 2 мм — чтобы клюв цыплёнка работал, а не мял.",
            "0–10 kun. Bu bosqichda yo poydevor qoʻyamiz, yo qolgan 35 kunni quvib boramiz. Yuqori protein, aniq lizin va metionin, 2 mm granula — joʻja tumshugʻi maydalamasdan ishlasin uchun.",
            "Days 0–10. This is where we either build the foundation or spend the next 35 days catching up. High protein, careful lysine and methionine, 2 mm crumble — so a chick's beak works the feed, not crushes it.",
        )),
    ("broiler-grow", _tri("Рост (бройлер)", "Oʻsish (broyler)", "Grower (broiler)"), Direction.BROILER, "broiler",
        _tri(
            "11–24 дня. Каркас уже стоит, теперь набираем мышцу. Энергия выше, протеин чуть ниже стартера, гранула 3 мм. Это рабочая лошадка цикла — здесь делается основная масса.",
            "11–24 kun. Skelet allaqachon turibdi, endi mushak terib boramiz. Energiya yuqori, protein starterdan biroz past, granula 3 mm. Bu sikldagi ishchi ot — asosiy massa shu yerda yigʻiladi.",
            "Days 11–24. The frame is in; now we put muscle on it. More energy, slightly less protein than the starter, 3 mm pellet. This is the workhorse of the cycle — most of the mass is built here.",
        )),
    ("broiler-finish", _tri("Финиш (бройлер)", "Yakuniy (broyler)", "Finisher (broiler)"), Direction.BROILER, "broiler",
        _tri(
            "25+ дней. Финиш — это не «домучить», это собрать привесы и FCR в одну строку отчёта. Максимум энергии, чистая выходная гигиена, ноль дней вывода для антибиотиков (потому что их там нет).",
            "25+ kun. Yakun — «zoʻr-bazoʻr tugatish» emas, balki vazn ortishi va FCRni hisobotning bitta qatoriga yigʻish. Maksimal energiya, toza chiqish gigiyenasi, antibiotiklar uchun 0 kun chiqarish davri (chunki ular u yerda yoʻq).",
            "Days 25+. The finisher isn't about «pushing through»; it's about packing weight and FCR into a single line of the report. Maximum energy, clean withdrawal hygiene, zero withdrawal days for antibiotics (because there aren't any).",
        )),
    ("layer-rear", _tri("Молодка (несушка)", "Yosh tovuq", "Pullet (layer)"), Direction.LAYER, "layer",
        _tri(
            "0–17 недель. Здесь куются три вещи: костяк, печень и однородность стада. Если сейчас где-то протекает — на пике это вылезет потерянным процентом яйцекладки. Мы это знаем по своим стадам.",
            "0–17 hafta. Bu yerda uchta narsa quyiladi: skelet, jigar va podaning bir xilligi. Agar hozir biror joyda «oqib» ketsa — choʻqqida bu yoʻqolgan tuxum unumdorligi sifatida koʻrinadi. Bizning podalarimiz buni bizga oʻrgatdi.",
            "Weeks 0–17. Three things are forged here: the frame, the liver, and flock uniformity. A leak at this stage shows up at peak as lost laying percentage. Our own flocks taught us this the hard way.",
        )),
    ("layer-pre", _tri("Предкладка", "Tuxum oldi", "Pre-layer"), Direction.LAYER, "layer",
        _tri(
            "17–19 недель. Окно в две недели, чтобы поднять кальций до 2.5% и подготовить организм к старту. Поторопиться — получить мягкую скорлупу, опоздать — потерять яйценоскость на разгоне.",
            "17–19 hafta. Ikki haftalik oyna — kaltsiyni 2.5% gacha koʻtarish va organizmni boshlanishga tayyorlash uchun. Shoshilib bersangiz — yumshoq poʻchoq olasiz, kechiksangiz — boshlanishda tuxum unumdorligini yoʻqotasiz.",
            "Weeks 17–19. A two-week window to ramp calcium to 2.5% and prep the bird for laying. Rush it — soft shells. Miss it — you lose laying percentage on the upswing.",
        )),
    ("layer-peak", _tri("Пик яйцекладки", "Choʻqqi davri", "Peak layer"), Direction.LAYER, "layer",
        _tri(
            "19–45 недель. Главное яйцо стада — здесь. Кальций 4.0–4.2%, крупная фракция известняка для медленного релиза ночью, выверенный лизин-метионин и витамин D3 для скорлупы.",
            "19–45 hafta. Podaning asosiy tuxumi shu yerda. Kaltsiy 4.0–4.2%, kechasi sekin chiqishi uchun yirik fraksiyali ohaktosh, aniq lizin-metionin va poʻchoq uchun D3 vitamini.",
            "Weeks 19–45. The flock's main egg lives here. Calcium 4.0–4.2%, coarse limestone for slow overnight release, tight lysine-methionine and vitamin D3 for the shell.",
        )),
    ("layer-post", _tri("Постпик", "Choʻqqidan keyin", "Post-peak"), Direction.LAYER, "layer",
        _tri(
            "45+ недель. Стадо устаёт, скорлупа тоже. Здесь корм работает уже не «на разгон», а «на удержание»: больше кальция, больше D3, меньше энергии, больше витамина E.",
            "45+ hafta. Pod ham, poʻchoq ham charchayapti. Bu yerda yem «tezlatish uchun» emas, «ushlab turish uchun» ishlaydi: koʻproq kaltsiy, koʻproq D3, kamroq energiya, koʻproq E vitamini.",
            "Weeks 45+. The flock tires; so does the shell. Feed switches from «pushing» to «holding»: more calcium, more D3, less energy, more vitamin E.",
        )),
    ("parent-rear", _tri("Родители: рост", "Ota-ona: oʻsish", "Parent: rearing"), Direction.PARENT, "parent",
        _tri(
            "Контролируемый рост ремонтного молодняка с ежедневным взвешиванием. Цель — однородность стада >85% и чистая кривая массы тела. То, что не сложилось здесь, не починится потом.",
            "Yoshlarni har kuni tortish bilan nazoratli oʻsishi. Maqsad — pod bir xilligi >85% va vazn egri chizigʻining toza shakli. Bu yerda yigʻilmagan narsa keyinchalik tuzatilmaydi.",
            "Controlled rearing with daily weighing. The goal: flock uniformity above 85% and a clean body-weight curve. What doesn't come together here can't be fixed later.",
        )),
    ("parent-breeder", _tri("Родители: племенной", "Ota-ona: nasldor", "Parent: breeder"), Direction.PARENT, "parent",
        _tri(
            "Период яйцекладки родительского стада. Мы выводим не яйцо — мы выводим следующее поколение бройлеров. Витамины Е, А, D3 в работающих дозировках — фермент гормонального уровня, а не строка состава.",
            "Ota-ona podasining tuxum davri. Biz tuxum emas — keyingi avlod broyler chiqarmoqdamiz. E, A, D3 vitaminlari ishlaydigan dozalarda — gormonal darajadagi ferment, tarkib qatori emas.",
            "Parent-stock laying. We're not producing eggs — we're producing the next generation of broilers. Vitamins E, A and D3 are dosed at hormonal-grade levels, not just on the label.",
        )),
]

# ── Товары ─────────────────────────────────────────────────────────────────
PRODUCTS = [
    {"code": "starter-broiler-23", "brand": "yembro", "category": "broiler-start", "direction": Direction.BROILER,
     "names": _tri("Стартер 23 для бройлеров", "Broyler uchun Starter 23", "Broiler Starter 23"),
     "short": _tri(
         "Полнорационный стартер 0–10 дней. Протеин 23%, обменная энергия 3050 ккал/кг.",
         "Toʻliq ratsionli boshlanish 0–10 kun. Protein 23%, almashinuv energiyasi 3050 kkal/kg.",
         "Complete starter for days 0–10. Protein 23%, ME 3050 kcal/kg.",
     ),
     "long": _tri(
         "Первая неделя бройлера решает половину итогового результата — и здесь нельзя экономить ни на сое, ни на рыбной муке. Мелкая гранула 2 мм для маленького клюва, легкоусвояемые белки, полный витаминный профиль, которого хватает на старт желудка и иммунитета. Целевой FCR на 0–10 день — 0.85. Делаем под программу Cobb 500.",
         "Broylerning birinchi haftasi yakuniy natijaning yarmini hal qiladi — bu yerda na soyada, na baliq unida tejash mumkin emas. Kichik tumshuq uchun 2 mm mayda granula, oson hazm boʻladigan oqsillar, oshqozonni va immunitetni boshlash uchun yetarli toʻliq vitamin tarkibi. 0–10 kun maqsadli FCR — 0.85. Cobb 500 dasturi uchun.",
         "The first week sets half of the broiler's final result — and you don't get to save on soy or fish meal here. A small 2 mm crumble for a small beak, easily digestible proteins, a vitamin profile rich enough to wake up both gut and immunity. Target FCR 0–10 days — 0.85. Built for the Cobb 500 program.",
     ),
     "package": 25, "age": (0, 10), "featured": True,
     "spec": {"protein_pct": 23.0, "fat_pct": 6.0, "fiber_pct": 4.0, "lysine_pct": 1.42, "methionine_pct": 0.55, "me_kcal_per_kg": 3050, "calcium_pct": 0.95, "phosphorus_pct": 0.48, "moisture_pct": 12.5}},

    {"code": "grower-broiler-21", "brand": "yembro", "category": "broiler-grow", "direction": Direction.BROILER,
     "names": _tri("Гроуэр 21 для бройлеров", "Broyler uchun Grower 21", "Broiler Grower 21"),
     "short": _tri(
         "Корм для активного роста 11–24 дня. Протеин 21%, гранула 3 мм.",
         "Aktiv oʻsish yemi 11–24 kun. Protein 21%, granula 3 mm.",
         "Active-growth feed for days 11–24. Protein 21%, 3 mm pellet.",
     ),
     "long": _tri(
         "Здесь делается основная мышечная масса. Протеин снижен до 21%, энергия поднята до 3150 ккал/кг — идёт работа на привес, а не на «прокорм». Гранула 3 мм поедается без потерь, без пыли в кормораздатчике. Программа стыкуется со стартером 23 без переходного скачка.",
         "Bu yerda asosiy mushak massasi yigʻiladi. Protein 21% gacha tushirilgan, energiya 3150 kkal/kg gacha koʻtarilgan — vazn ortishi uchun ishlaydi, «toʻyish uchun» emas. 3 mm granula yoʻqotishlarsiz yeyiladi, yem tarqatkichda chang qoldirmaydi. Dastur Starter 23 bilan oʻtkinchi sakrashsiz birikadi.",
         "This is where most of the muscle mass is built. Protein steps down to 21%, energy steps up to 3150 kcal/kg — the bird grows, it doesn't just eat. The 3 mm pellet feeds clean — no dust in the line. Program flows from Starter 23 without a transition spike.",
     ),
     "package": 40, "age": (11, 24), "featured": True,
     "spec": {"protein_pct": 21.0, "fat_pct": 7.5, "fiber_pct": 4.5, "lysine_pct": 1.25, "methionine_pct": 0.50, "me_kcal_per_kg": 3150, "calcium_pct": 0.85, "phosphorus_pct": 0.42, "moisture_pct": 12.5}},

    {"code": "finisher-broiler-19", "brand": "yembro", "category": "broiler-finish", "direction": Direction.BROILER,
     "names": _tri("Финишер 19 для бройлеров", "Broyler uchun Finisher 19", "Broiler Finisher 19"),
     "short": _tri(
         "Финишный корм 25+ дней. Максимальная энергия и низкий FCR без антибиотиков.",
         "Yakuniy yem 25+ kun. Maksimal energiya va past FCR, antibiotiksiz.",
         "Finisher for days 25+. Max energy, low FCR, no antibiotics.",
     ),
     "long": _tri(
         "На последнем отрезке цикла мы зарабатываем — или теряем — те самые сотые доли FCR. Энергия 3200 ккал/кг при сниженном протеине — точная балансировка под привес и качество тушки. Без АБ, период вывода — ноль дней. Корм-партиёнок: каждая прибавка кг становится прибылью.",
         "Sikllning oxirgi qismida biz ana shu FCRning yuzdan bir ulushlarini ishlab topamiz — yoki yoʻqotamiz. Past protein bilan 3200 kkal/kg energiya — vazn ortishi va goʻsht sifati uchun aniq balans. Antibiotiklarsiz, chiqarish davri — nol kun. Sherik-yem: har kg qoʻshimcha foydaga aylanadi.",
         "The final stretch is where the last hundredths of FCR are earned — or lost. 3200 kcal/kg of energy paired with reduced protein, balanced for weight gain and carcass quality. No antibiotics, zero withdrawal days. A partner feed — every extra kilogram becomes profit.",
     ),
     "package": 40, "age": (25, 42), "featured": True,
     "spec": {"protein_pct": 19.0, "fat_pct": 8.5, "fiber_pct": 4.5, "lysine_pct": 1.10, "methionine_pct": 0.45, "me_kcal_per_kg": 3200, "calcium_pct": 0.80, "phosphorus_pct": 0.40, "moisture_pct": 12.5}},

    {"code": "pullet-rear", "brand": "yembro", "category": "layer-rear", "direction": Direction.LAYER,
     "names": _tri("Корм для молодки", "Yosh tovuq yemi", "Pullet feed"),
     "short": _tri(
         "0–17 недель. Поэтапная программа: костяк, печень, однородность.",
         "0–17 hafta. Bosqichli dastur: skelet, jigar, bir xillik.",
         "Weeks 0–17. Phased program: frame, liver, uniformity.",
     ),
     "long": _tri(
         "Молодка — это инвестиция, которую мы окупаем потом, на пике. Поэтому здесь не торопим рост, не «забиваем» энергией, не разбалтываем кальций. Программа разложена на возрастные фазы, чтобы стадо подошло к старту яйцекладки в одном весе и одной готовности. Подходит для Hy-Line Brown и Lohmann LSL.",
         "Yosh tovuq — bu choʻqqida qaytib oladigan sarmoya. Shuning uchun bu yerda oʻsishni shoshmaymiz, energiya bilan «koʻmib» tashlamaymiz, kaltsiyni «buzmaymiz». Dastur yosh fazalariga ajratilgan — pod tuxum boshlanishiga bir xil vazn va bir xil tayyorgarlikda kelishi uchun. Hy-Line Brown va Lohmann LSL uchun.",
         "Pullets are an investment that pays back at peak. So we don't rush the growth, we don't bulldoze it with energy, we don't shake the calcium. The program splits across age phases so the flock reaches laying in one weight and one readiness. Built for Hy-Line Brown and Lohmann LSL.",
     ),
     "package": 40, "age": (0, 119), "featured": False,
     "spec": {"protein_pct": 17.5, "fat_pct": 4.0, "fiber_pct": 5.5, "lysine_pct": 0.95, "methionine_pct": 0.42, "me_kcal_per_kg": 2800, "calcium_pct": 1.10, "phosphorus_pct": 0.50, "moisture_pct": 12.5}},

    {"code": "pre-layer", "brand": "yembro", "category": "layer-pre", "direction": Direction.LAYER,
     "names": _tri("Предкладка", "Tuxum oldi", "Pre-layer"),
     "short": _tri(
         "За две недели до старта яйцекладки. Кальций уверенно идёт вверх.",
         "Tuxum boshlanishidan ikki hafta oldin. Kaltsiy ishonchli ravishda koʻtariladi.",
         "Two weeks before laying onset. Calcium ramps up — confidently.",
     ),
     "long": _tri(
         "Эти 14 дней — самые недооценённые в цикле. Поднимаем кальций до 2.5%, активируем печень, готовим скелет к выниманию минералов. Если этот переход смазать — первые яйца будут с тонкой скорлупой и стрессом для несушки.",
         "Bu 14 kun siklda eng kamida qadrlanadigan davr. Kaltsiyni 2.5% gacha koʻtaramiz, jigarni faollashtiramiz, skeletni minerallarning tortib olinishiga tayyorlaymiz. Agar bu oʻtish noqulay boʻlsa — birinchi tuxumlar yupqa poʻchoqli va tovuq uchun stress bilan boʻladi.",
         "These 14 days are the most underrated in the cycle. We push calcium to 2.5%, wake up the liver, prep the skeleton for mineral mobilization. Smear this handover — and the first eggs come out with thin shells and a stressed bird.",
     ),
     "package": 40, "age": (120, 140), "featured": False,
     "spec": {"protein_pct": 17.5, "fat_pct": 4.0, "fiber_pct": 5.0, "calcium_pct": 2.50, "phosphorus_pct": 0.55, "me_kcal_per_kg": 2750, "moisture_pct": 12.5}},

    {"code": "layer-peak-17", "brand": "yembro", "category": "layer-peak", "direction": Direction.LAYER,
     "names": _tri("Пик яйцекладки 17", "Choʻqqi davri 17", "Peak layer 17"),
     "short": _tri(
         "Пиковая фаза. Протеин 17%, кальций 4.0%. Скорлупа по высшему разряду.",
         "Choʻqqi davri. Protein 17%, kaltsiy 4.0%. Yuqori sifatdagi poʻchoq.",
         "Peak phase. Protein 17%, calcium 4.0%. Shell, top grade.",
     ),
     "long": _tri(
         "Здесь стадо отдаёт максимум — и здесь лучше всего видно, что в корме сделано правильно. Кальций ведём двумя фракциями: мелкая для пищеварения днём, крупная для медленного релиза ночью, когда формируется скорлупа. Витамин D3 на верхней рабочей границе. Программа Hy-Line W-36.",
         "Bu yerda pod maksimumni beradi — va bu yerda yemda nimalar toʻgʻri qilinganligi eng yaxshi koʻrinadi. Kaltsiyni ikki fraksiyada olib boramiz: kunduzgi hazm uchun mayda, kechqurun poʻchoq shakllanishi uchun sekin chiqadigan yirik. D3 vitamini yuqori ishchi chegarada. Hy-Line W-36 dasturi.",
         "This is where the flock delivers — and where the feed shows whether it was built right. Calcium splits into two fractions: fine for daytime digestion, coarse for slow overnight release as the shell forms. Vitamin D3 at the upper working bound. Hy-Line W-36 program.",
     ),
     "package": 40, "age": (141, 315), "featured": True,
     "spec": {"protein_pct": 17.0, "fat_pct": 4.5, "fiber_pct": 5.0, "lysine_pct": 0.85, "methionine_pct": 0.40, "me_kcal_per_kg": 2700, "calcium_pct": 4.00, "phosphorus_pct": 0.50, "moisture_pct": 12.5}},

    {"code": "layer-post-peak", "brand": "yembro", "category": "layer-post", "direction": Direction.LAYER,
     "names": _tri("Постпик", "Choʻqqidan keyin", "Post-peak"),
     "short": _tri(
         "После 45 недель. Скорлупа держит форму, стадо не теряет тонус.",
         "45 haftadan keyin. Poʻchoq shaklini saqlaydi, pod tonusini yoʻqotmaydi.",
         "After week 45. The shell holds, the flock holds.",
     ),
     "long": _tri(
         "Со второй половины цикла птица начинает «уставать», и наша задача — не дать ей рассыпаться. Кальций 4.2% с упором на крупную фракцию. Витамин Е и селен — для антиоксидантной защиты. Энергия чуть ниже — лишний вес сейчас не нужен.",
         "Siklning ikkinchi yarmidan parranda «charchashni» boshlaydi, bizning vazifamiz — uni «toʻkilib» ketishiga yoʻl qoʻymaslik. Kaltsiy 4.2%, yirik fraksiyaga eʼtibor bilan. E vitamini va selen — antioksidant himoya uchun. Energiya biroz past — keraksiz vazn endi shart emas.",
         "From the second half of the cycle the bird starts to tire — our job is to keep her from coming apart. Calcium 4.2%, weighted toward the coarse fraction. Vitamin E and selenium for antioxidant cover. Energy a touch lower — extra weight isn't useful now.",
     ),
     "package": 40, "age": (316, 500), "featured": False,
     "spec": {"protein_pct": 16.0, "fat_pct": 4.5, "fiber_pct": 5.5, "calcium_pct": 4.20, "phosphorus_pct": 0.45, "me_kcal_per_kg": 2680, "moisture_pct": 12.5}},

    {"code": "parent-rearing", "brand": "yembro", "category": "parent-rear", "direction": Direction.PARENT,
     "names": _tri("Родители: рост", "Ota-ona: oʻsish", "Parent: rearing"),
     "short": _tri(
         "Контролируемый рост, фокус на однородность стада >85%.",
         "Nazoratli oʻsish, pod bir xilligi >85% ga eʼtibor.",
         "Controlled rearing, flock uniformity above 85%.",
     ),
     "long": _tri(
         "Родителей растят не «на килограммы», а «на график». Каждая неделя — своя цифра массы тела, проверка по карте и поправка на следующий день, если стадо ушло вверх или вниз. Корм здесь — это инструмент дисциплины, а не калорий.",
         "Ota-onalarni «kilogrammga» emas, «jadvalga» oʻstirishadi. Har hafta — vazn boʻyicha oʻz raqami, kartochka boʻyicha tekshirish va agar pod yuqoriga yoki pastga ketgan boʻlsa — ertangi kunga tuzatish. Bu yerda yem — kaloriyalar emas, intizom asbobidir.",
         "Parents aren't grown «for kilos», they're grown «to a curve». Every week has its body-weight number, you check it against the chart and adjust tomorrow's feed if the flock drifted up or down. Feed here is a discipline tool, not a calorie source.",
     ),
     "package": 40, "age": (0, 140), "featured": False,
     "spec": {"protein_pct": 18.0, "fat_pct": 4.5, "fiber_pct": 5.5, "lysine_pct": 0.95, "methionine_pct": 0.40, "me_kcal_per_kg": 2800, "calcium_pct": 1.00, "phosphorus_pct": 0.45, "moisture_pct": 12.5}},

    {"code": "parent-breeder", "brand": "yembro", "category": "parent-breeder", "direction": Direction.PARENT,
     "names": _tri("Родители: племенной", "Ota-ona: nasldor", "Parent: breeder"),
     "short": _tri(
         "Период яйцекладки родителей. Качество инкубационного яйца на первом месте.",
         "Ota-onalarning tuxum davri. Inkubatsiya tuxumi sifati birinchi oʻrinda.",
         "Parent laying period. Hatchability comes first.",
     ),
     "long": _tri(
         "Корм для тех, кто кормит не яйцо, а будущего бройлера. Витамин Е поднят, А и D3 в работающих дозировках, кальций — в умеренной верхней границе. Цель — крепкая скорлупа и высокий процент вывода в инкубаторе.",
         "Tuxum emas, kelgusi broylerni boqayotganlar uchun yem. E vitamini koʻtarilgan, A va D3 ishlaydigan dozalarda, kaltsiy — ishchi yuqori chegara. Maqsad — mustahkam poʻchoq va inkubatorda yuqori chiqim.",
         "Feed for those who aren't feeding eggs, they're feeding the next broiler generation. Elevated vitamin E, A and D3 dosed to work, calcium at the high end of the working range. Target: strong shells and high hatchability.",
     ),
     "package": 40, "age": (141, 500), "featured": False,
     "spec": {"protein_pct": 16.0, "fat_pct": 4.0, "fiber_pct": 5.5, "calcium_pct": 3.50, "phosphorus_pct": 0.50, "me_kcal_per_kg": 2750, "moisture_pct": 12.5}},

    {"code": "pro-starter-24", "brand": "yembro-pro", "category": "broiler-start", "direction": Direction.BROILER,
     "names": _tri("Pro Старт 24", "Pro Boshlanish 24", "Pro Starter 24"),
     "short": _tri(
         "Премиум-стартер 24% протеина для интенсивного откорма.",
         "Intensiv boqish uchun 24% proteinli premium boshlanish yemi.",
         "Premium starter at 24% protein, for intensive operations.",
     ),
     "long": _tri(
         "Когда бройлеру некогда раскачиваться. Лизин 1.50%, метионин 0.60%, треонин 1.00% — расширенный аминокислотный профиль, который не оставляет цыплёнку ни одной причины расти медленно. Целевой FCR на старте — 0.85, и мы видели его в чужих отчётах с этим кормом.",
         "Broylerga «sekinlashishga» vaqti yoʻq paytda. Lizin 1.50%, metionin 0.60%, treonin 1.00% — joʻjaga sekin oʻsishga hech qanday sabab qoldirmaydigan kengaytirilgan aminokislota tarkibi. Boshlanishdagi maqsadli FCR — 0.85, va biz buni shu yem bilan boshqalarning hisobotlarida koʻrganmiz.",
         "Built for broilers that don't have time to ramp up. Lysine 1.50%, methionine 0.60%, threonine 1.00% — an extended amino-acid profile that leaves a chick no excuse to grow slowly. Target starter FCR — 0.85, and we've seen it on other farms' dashboards.",
     ),
     "package": 25, "age": (0, 10), "featured": True,
     "spec": {"protein_pct": 24.0, "fat_pct": 6.5, "fiber_pct": 3.8, "lysine_pct": 1.50, "methionine_pct": 0.60, "me_kcal_per_kg": 3100, "calcium_pct": 1.00, "phosphorus_pct": 0.50, "moisture_pct": 12.0}},

    {"code": "pro-grower-22", "brand": "yembro-pro", "category": "broiler-grow", "direction": Direction.BROILER,
     "names": _tri("Pro Гроуэр 22", "Pro Grower 22", "Pro Grower 22"),
     "short": _tri(
         "Плотная энергия и протеин 22%. Для серьёзных птицефабрик.",
         "Zich energiya va 22% protein. Jiddiy parrandachilik fabrikalari uchun.",
         "Dense energy, 22% protein. For operations that mean it.",
     ),
     "long": _tri(
         "Соя, кукуруза, рыбная мука — без растительных «дублёров» сомнительного происхождения. Энергия 3200 ккал/кг, аминокислоты на верхней рабочей границе. Это корм не для эксперимента — для регулярных партий с таблицами.",
         "Soya, makkajoʻxori, baliq uni — shubhali kelib chiqishga ega oʻsimlik «oʻrnini bosadiganlar» yoʻq. Energiya 3200 kkal/kg, aminokislotalar yuqori ishchi chegarada. Bu eksperiment uchun emas — jadvalli muntazam partiyalar uchun yem.",
         "Soy, corn, fish meal — no questionable plant substitutes. Energy 3200 kcal/kg, amino acids at the upper working bound. This isn't a feed for an experiment — it's for the regular flock with weekly numbers.",
     ),
     "package": 40, "age": (11, 24), "featured": True,
     "spec": {"protein_pct": 22.0, "fat_pct": 8.0, "fiber_pct": 4.0, "lysine_pct": 1.35, "methionine_pct": 0.55, "me_kcal_per_kg": 3200, "calcium_pct": 0.90, "phosphorus_pct": 0.45, "moisture_pct": 12.0}},

    {"code": "pro-finisher-20", "brand": "yembro-pro", "category": "broiler-finish", "direction": Direction.BROILER,
     "names": _tri("Pro Финишер 20", "Pro Finisher 20", "Pro Finisher 20"),
     "short": _tri(
         "Премиум-финишер. Энергия 3250 ккал/кг, привесы +5%.",
         "Premium finisher. Energiya 3250 kkal/kg, vazn ortishi +5%.",
         "Premium finisher. Energy 3250 kcal/kg, +5% on growth.",
     ),
     "long": _tri(
         "Финиш, в котором каждый грамм сделан на верхней рабочей мощности рецепта. Аминокислоты — лизин и метионин — рассчитаны под конкретные привесы у Cobb 500. Программа без АБ и кокцидиостатиков, готовая под выпуск премиум-сегмента.",
         "Har bir gramm retseptning yuqori ishchi quvvatida tayyorlangan yakun. Aminokislotalar — lizin va metionin — Cobb 500 ning aniq vazn ortishlariga moʻljallangan. Antibiotik va kokkidiostatiksiz dastur, premium-segment uchun tayyor.",
         "A finisher built at the top working margin of the recipe. Lysine and methionine pegged to specific Cobb 500 weight gains. No antibiotics, no coccidiostats — ready for premium-segment release.",
     ),
     "package": 40, "age": (25, 42), "featured": False,
     "spec": {"protein_pct": 20.0, "fat_pct": 9.0, "fiber_pct": 4.0, "lysine_pct": 1.20, "methionine_pct": 0.50, "me_kcal_per_kg": 3250, "calcium_pct": 0.85, "phosphorus_pct": 0.42, "moisture_pct": 12.0}},

    {"code": "pro-layer-peak-18", "brand": "yembro-pro", "category": "layer-peak", "direction": Direction.LAYER,
     "names": _tri("Pro Пик 18", "Pro Choʻqqi 18", "Pro Peak 18"),
     "short": _tri(
         "Пик 95%+ интенсивности. Усиленный витаминный профиль.",
         "95%+ intensivlik bilan choʻqqi. Kuchaytirilgan vitamin tarkibi.",
         "Peak at 95%+ intensity. Reinforced vitamin profile.",
     ),
     "long": _tri(
         "Корм для несушек, которым ставят план «выше среднего» — и от которых ждут красивый жёлток вне зависимости от сезона. Витамины Е, А, В12 в усиленных дозировках, селен в органической форме, цинк — для цвета желтка и здоровья оперения.",
         "«Oʻrtachadan yuqori» reja qoʻyilgan va fasldan qatʼiy nazar chiroyli sariq tuxum kutiladigan tovuqlar uchun yem. E, A, B12 vitaminlari kuchaytirilgan dozalarda, selen organik shaklda, sink — tuxum rangi va patlar sogʻligʻi uchun.",
         "Feed for layers held to an «above-average» plan — and expected to keep yolk color regardless of season. Vitamins E, A, B12 elevated, organic selenium, zinc for yolk color and feathering health.",
     ),
     "package": 40, "age": (141, 315), "featured": True,
     "spec": {"protein_pct": 18.0, "fat_pct": 5.0, "fiber_pct": 4.5, "lysine_pct": 0.92, "methionine_pct": 0.45, "me_kcal_per_kg": 2780, "calcium_pct": 4.20, "phosphorus_pct": 0.55, "moisture_pct": 12.0}},

    {"code": "bio-starter-22", "brand": "yembro-bio", "category": "broiler-start", "direction": Direction.BROILER,
     "names": _tri("Bio Стартер 22", "Bio Starter 22", "Bio Starter 22"),
     "short": _tri(
         "Без АБ и кокцидиостатиков. Орегано, бутираты, пробиотики.",
         "Antibiotik va kokkidiostatiksiz. Origano, butiratlar, probiotiklar.",
         "No antibiotics, no coccidiostats. Oregano, butyrates, probiotics.",
     ),
     "long": _tri(
         "Стартер, который растит чистого бройлера без химической поддержки кишечника. Эфирные масла орегано и тимьяна работают как природный антимикробный фон. Защищённая бутировая кислота кормит энтероциты. Bacillus subtilis заселяет кишечник нужной микрофлорой с первого дня.",
         "Ichakni kimyoviy qoʻllab-quvvatlashsiz toza broyler oʻstiradigan starter. Origano va timyan efir moylari tabiiy antimikrob fon sifatida ishlaydi. Himoyalangan moy kislotasi enterotsitlarni boqadi. Bacillus subtilis ichakni birinchi kundan kerakli mikroflora bilan toʻldiradi.",
         "A starter that raises a clean broiler without chemical gut props. Oregano and thyme oils act as a natural antimicrobial backdrop. Protected butyric acid feeds the enterocytes. Bacillus subtilis seeds the gut from day one.",
     ),
     "package": 25, "age": (0, 10), "featured": True,
     "spec": {"protein_pct": 22.0, "fat_pct": 6.0, "fiber_pct": 4.2, "lysine_pct": 1.40, "methionine_pct": 0.55, "me_kcal_per_kg": 3000, "calcium_pct": 0.95, "phosphorus_pct": 0.48, "moisture_pct": 12.5}},

    {"code": "bio-grower-20", "brand": "yembro-bio", "category": "broiler-grow", "direction": Direction.BROILER,
     "names": _tri("Bio Гроуэр 20", "Bio Grower 20", "Bio Grower 20"),
     "short": _tri(
         "Натуральные подкислители и фитогеники. Кишечник чист — стадо стабильно.",
         "Tabiiy kislotalantirgich va fitogeniklar. Ichak toza — pod barqaror.",
         "Natural acidifiers and phytogenics. Clean gut, steady flock.",
     ),
     "long": _tri(
         "Гроуэр, в котором мы держим микрофлору без антибиотиков, и стадо отвечает стабильным ростом. Органические кислоты, фитогенный комплекс, защищённая бутировая кислота. То, чем кормят бройлера, который потом будет лежать на полке с лейблом «без АБ».",
         "Antibiotiksiz mikroflorani saqlaymiz, va pod barqaror oʻsish bilan javob beradi. Organik kislotalar, fitogen kompleks, himoyalangan moy kislotasi. Keyin «AB-siz» yorlik bilan javonda yotadigan broylerni boqadigan yem.",
         "A grower that holds the microflora steady without antibiotics — and the flock answers with steady growth. Organic acids, phytogenic complex, protected butyric acid. The feed for a broiler that ends up on the shelf with a «no-AB» label.",
     ),
     "package": 40, "age": (11, 24), "featured": False,
     "spec": {"protein_pct": 20.5, "fat_pct": 7.0, "fiber_pct": 4.5, "lysine_pct": 1.20, "methionine_pct": 0.48, "me_kcal_per_kg": 3100, "calcium_pct": 0.85, "phosphorus_pct": 0.42, "moisture_pct": 12.5}},

    {"code": "bio-finisher-18", "brand": "yembro-bio", "category": "broiler-finish", "direction": Direction.BROILER,
     "names": _tri("Bio Финишер 18", "Bio Finisher 18", "Bio Finisher 18"),
     "short": _tri(
         "Финиш без АБ. Натуральный цвет тушки за счёт каротиноидов бархатцев.",
         "Antibiotiksiz yakun. Bahor guli karotinoidlari hisobiga tabiiy goʻsht rangi.",
         "AB-free finisher. Natural carcass color from marigold carotenoids.",
     ),
     "long": _tri(
         "Финишер для эко-сегмента. Натуральные каротиноиды бархатцев дают тёплый жёлтый оттенок тушки — без синтетических красителей. Энергия достаточная для финального набора, без перекоса.",
         "Eko-segment uchun finisher. Bahor guli tabiiy karotinoidlari sintetik boʻyoqlarsiz goʻshtga issiq sariq tus beradi. Yakuniy yigʻish uchun yetarli energiya, chetga chiqishlarsiz.",
         "Finisher for the eco segment. Natural marigold carotenoids give the carcass a warm yellow tone — without synthetic colorants. Energy is enough for the final pack-on, with no excess.",
     ),
     "package": 40, "age": (25, 42), "featured": False,
     "spec": {"protein_pct": 18.0, "fat_pct": 8.0, "fiber_pct": 4.5, "lysine_pct": 1.05, "methionine_pct": 0.42, "me_kcal_per_kg": 3150, "calcium_pct": 0.80, "phosphorus_pct": 0.40, "moisture_pct": 12.5}},

    {"code": "bio-layer", "brand": "yembro-bio", "category": "layer-peak", "direction": Direction.LAYER,
     "names": _tri("Bio Несушка", "Bio Tovuq yemi", "Bio Layer"),
     "short": _tri(
         "Корм для премиум-яйца «без АБ». Жёлток глубокого, насыщенного цвета.",
         "«AB-siz» premium tuxum yemi. Tuxum sarigʻi chuqur, toʻq rangda.",
         "Feed for premium «no-AB» eggs. Deep, rich yolk color.",
     ),
     "long": _tri(
         "Корм для производителей яйца премиум-сегмента, где этикетка «без антибиотиков» — не маркетинг, а факт. Натуральные источники каротиноидов (бархатцы и красный перец) дают желтку насыщенный цвет, который сразу видно на полке.",
         "Yorlikdagi «antibiotiksiz» — marketing emas, balki dalil boʻlgan premium tuxum ishlab chiqaruvchilari uchun yem. Tabiiy karotinoid manbalari (bahor guli va qizil qalampir) tuxum sarigʻiga javonda darhol koʻrinadigan toʻyingan rang beradi.",
         "Feed for premium-egg producers where «no antibiotics» is a fact, not marketing. Natural carotenoid sources — marigold and red pepper — give the yolk the saturated color buyers spot on the shelf.",
     ),
     "package": 40, "age": (141, 500), "featured": True,
     "spec": {"protein_pct": 17.0, "fat_pct": 4.5, "fiber_pct": 5.0, "lysine_pct": 0.85, "methionine_pct": 0.40, "me_kcal_per_kg": 2700, "calcium_pct": 4.00, "phosphorus_pct": 0.50, "moisture_pct": 12.5}},

    {"code": "premix-broiler-1pct", "brand": "yembro", "category": "premix", "direction": Direction.BROILER,
     "names": _tri("Премикс для бройлеров 1%", "Broyler uchun premiks 1%", "Broiler premix 1%"),
     "short": _tri(
         "Витамины + микроэлементы + фитаза. Ввод 1% в собственный замес.",
         "Vitaminlar + mikroelementlar + fitaza. Oʻz zamesga 1% kiritish.",
         "Vitamins + trace minerals + phytase. 1% inclusion in your own mix.",
     ),
     "long": _tri(
         "Премикс для тех, кто варит корм у себя и не хочет «собирать пазл» из десятка отдельных добавок. Витамины А, D3, E, K, B-комплекс, микроэлементы (Fe, Cu, Mn, Zn, I, Se), холин и фитаза. Сделано так, чтобы 1% этой смеси закрывал всю микро-составляющую рациона.",
         "Yemni oʻzi tayyorlaydigan va oʻnlab alohida qoʻshimchalardan «pazl» yigʻishni xohlamaydiganlar uchun premiks. A, D3, E, K, B-kompleks vitaminlari, mikroelementlar (Fe, Cu, Mn, Zn, I, Se), xolin va fitaza. Bu aralashmaning 1%i ratsionning barcha mikro-tarkibiy qismini yopadigan qilib tayyorlangan.",
         "A premix for operators who mix their own feed and don't want to build a puzzle from ten separate add-ins. Vitamins A, D3, E, K and B-complex, trace minerals (Fe, Cu, Mn, Zn, I, Se), choline, phytase. Engineered so that 1% inclusion closes the entire micro-component of the ration.",
     ),
     "package": 25, "age": (None, None), "featured": False,
     "spec": {"extra": {"premix_inclusion_pct": 1.0, "vitamin_a_iu": 12_000_000, "vitamin_d3_iu": 4_000_000}}},

    {"code": "premix-layer-25pct", "brand": "yembro", "category": "premix", "direction": Direction.LAYER,
     "names": _tri("Премикс для несушек 2.5%", "Tovuq uchun premiks 2.5%", "Layer premix 2.5%"),
     "short": _tri(
         "Концентрат с готовым кальцием и фосфором. Карофиллы для жёлтка.",
         "Tayyor kaltsiy va fosfor bilan konsentrat. Sarigʻi uchun karofillar.",
         "Concentrate with calcium, phosphorus and yolk pigments built in.",
     ),
     "long": _tri(
         "Премикс с уже готовыми уровнями кальция и фосфора — вы не считаете отдельно карбонат и монокальцийфосфат, всё уже есть. Карофиллы (красный и жёлтый) дают желтку цвет 12 по шкале Roche. 2.5% ввода — и рецепт собран.",
         "Tayyor kaltsiy va fosfor darajalariga ega premiks — siz karbonat va monokaltsiyfosfatni alohida hisoblamaysiz, hammasi mavjud. Karofillar (qizil va sariq) tuxum sarigʻiga Roche shkalasi boʻyicha 12 rang beradi. 2.5% kiritish — va retsept yigʻildi.",
         "Premix with calcium and phosphorus already dialed in — no separate carbonate and monocalcium-phosphate math. Yellow and red carophyll bring the yolk to a Roche-scale 12. Inclusion at 2.5% — recipe done.",
     ),
     "package": 25, "age": (None, None), "featured": False,
     "spec": {"calcium_pct": 18.0, "phosphorus_pct": 4.5, "extra": {"premix_inclusion_pct": 2.5, "yolk_color_target": 12}}},
]

# ── Страницы ───────────────────────────────────────────────────────────────
PAGES = [
    ("about", _tri("О компании", "Kompaniya haqida", "About"), _tri(
        "Yembro начался не с офиса. Он начался с того, что мы кормили чужими комбикормами своих собственных бройлеров — и не понимали, почему две одинаковые партии птицы дают разный финальный вес. Зерно одинаковое. Климат одинаковый. Условия одинаковые. А корм каждый раз — чуть-чуть другой.\n\nТогда мы построили свой кормовой цех. Сначала — для себя. Потом — для соседей-фермеров. Потом — для крупных птицефабрик, которые тоже устали от сюрпризов.\n\nСегодня Yembro — это:\n\n• Полный цикл: входной QC сырья, рецептура, лабораторный контроль готовой партии, отгрузка\n• Программы под Cobb 500, Ross 308, Hy-Line W-36, Lohmann LSL\n• Контроль микотоксинов — DON, ZEN, AFB1 — на каждой партии зерна\n• Стабильность партий: отклонение протеина не превышает 0.5%\n• Доставка по всему Узбекистану в окне 24–72 часа\n• Зоотехник, который сопровождает стадо — а не «продал и ушёл»\n\nМы не «производитель кормов». Мы фермеры, которые научились делать корм правильно — и решили этим делиться.",
        "Yembro ofisdan boshlanmagan. U boshqa birovlarning yemi bilan oʻz broylerlarimizni boqib, ikki bir xil parranda partiyasi nima uchun har xil yakuniy vazn berishini tushunmaganimizdan boshlangan. Don bir xil. Iqlim bir xil. Sharoitlar bir xil. Yem esa har safar — bir oz boshqacha.\n\nShundan soʻng oʻz yem sexini qurdik. Avval — oʻzimiz uchun. Soʻng — qoʻshni fermerlar uchun. Keyin — sarpalardan charchagan yirik parrandachilik fabrikalari uchun.\n\nBugun Yembro — bu:\n\n• Toʻliq sikl: xom ashyo kirish QC, retsept, tayyor partiyani laboratoriya nazorati, ortish\n• Cobb 500, Ross 308, Hy-Line W-36, Lohmann LSL dasturlari\n• Mikotoksinlar nazorati — DON, ZEN, AFB1 — har bir don partiyasida\n• Partiyalar barqarorligi: protein chetga chiqishi 0.5% dan oshmaydi\n• Butun Oʻzbekiston boʻylab 24–72 soat ichida yetkazib berish\n• «Sotdi va ketdi» emas, podaga hamrohlik qiluvchi zootexnik\n\nBiz «yem ishlab chiqaruvchisi» emasmiz. Biz yemni toʻgʻri tayyorlashni oʻrgangan va buni boshqalar bilan boʻlishishga qaror qilgan fermerlarmiz.",
        "Yembro didn't start in an office. It started when we were feeding our own broilers with someone else's feed — and couldn't figure out why two identical flocks finished at different weights. Same grain. Same climate. Same setup. The feed, every time, was a little bit different.\n\nSo we built our own feed mill. First for ourselves. Then for neighboring farms. Then for the industrial operations that were also tired of surprises.\n\nToday Yembro is:\n\n• Full cycle: raw-material inbound QC, formulation, lab control of every finished batch, delivery\n• Programs aligned to Cobb 500, Ross 308, Hy-Line W-36, Lohmann LSL\n• Mycotoxin screening — DON, ZEN, AFB1 — on every grain batch\n• Batch stability: protein deviation never exceeds 0.5%\n• Nationwide delivery within 24–72 hours\n• A nutritionist who walks the flock with you — instead of «sold and gone»\n\nWe're not a «feed manufacturer». We're farmers who learned how to make feed properly — and decided to share it.",
    )),
    ("contacts", _tri("Контакты", "Aloqa", "Contacts"), _tri(
        "Звоните, пишите, заезжайте. Мы открыты для прямых разговоров — без call-центра и анкет.\n\nТелефон: +998 (90) 000-00-00\nTelegram: @yembro\nEmail: hello@yembro.uz\n\nПроизводство: Ташкентская область, Узбекистан\n\nМенеджеры на связи пн–сб, 09:00–18:00. После 18:00 — Telegram, ответим в течение часа в рабочее время недели.",
        "Qoʻngʻiroq qiling, yozing, kelib koʻring. Biz toʻgʻri suhbatlarga ochiqmiz — call-markaz va anketalarsiz.\n\nTelefon: +998 (90) 000-00-00\nTelegram: @yembro\nEmail: hello@yembro.uz\n\nIshlab chiqarish: Toshkent viloyati, Oʻzbekiston\n\nMenejerlar du–shb, 09:00–18:00 da aloqada. 18:00 dan keyin — Telegram, hafta ichida bir soat ichida javob beramiz.",
        "Call us, message us, drop by. We're open to straight conversations — no call center, no forms.\n\nPhone: +998 (90) 000-00-00\nTelegram: @yembro\nEmail: hello@yembro.uz\n\nMill: Tashkent Region, Uzbekistan\n\nManagers reachable Mon–Sat, 09:00–18:00. After hours — Telegram. We answer within an hour during the working week.",
    )),
    ("erp", _tri("ERP в аренду", "ERP ijaraga", "ERP for rent"), _tri(
        "Yembro ERP — это не очередная «программа для бизнеса». Это система, которую мы написали для собственной птицефабрики, потому что Excel перестал справляться, а коробочные ERP отказывались разговаривать на языке бройлера.\n\nЧто закрывает Yembro ERP:\n\n• Закупка сырья: зерно, шрот, премикс — с автоматическим расчётом усушки и контролем влажности\n• Цех кормов: рецепты, партии, лабораторный QC, фасовка по мешкам и силосам\n• Инкубация: яйцо в работе, биоконтроль, hatch rate с разбивкой по поставщикам\n• Откорм: посадка, кормление, падёж, FCR и ADG по дням\n• Маточник и несушка: яйценоскость, качество яйца, графики кальция\n• Забой: фасовка, выход тушки, прослеживаемость от партии до пакета\n• Продажи и склад с поддержкой нескольких юрлиц\n• Финансы: платежи, валютные курсы ЦБ, P&L по подразделениям\n• Дашборд KPI и Telegram-алёрты — оператор узнаёт о проблеме за минуту, а не за неделю\n\nКак подключаемся:\n\n• Заявка → демо → договор → рабочее место\n• Никаких внедренческих компаний. Никаких лицензий. Никаких «годовых сопровождений» поверх стоимости\n• От $200/мес за рабочее место. Запуск — один день\n\nERP, который вы арендуете, тестируется ежедневно у нас на ферме. Вы видите ровно ту же систему, которой мы пользуемся сами.",
        "Yembro ERP — bu navbatdagi «biznes uchun dastur» emas. Bu Excel chiday olmay qolgan, qutidagi ERPlar esa broyler tilida gaplashishni rad etgan paytda biz oʻz parrandachilik fabrikamiz uchun yozgan tizim.\n\nYembro ERP nimani yopadi:\n\n• Xom ashyo xaridi: don, shrot, premiks — namlik nazorati va avtomatik usushka hisobi bilan\n• Yem sexi: retseptlar, partiyalar, laboratoriya QC, qoplarga va silos joylashtirish\n• Inkubatsiya: ishdagi tuxum, bionazorat, yetkazib beruvchilar boʻyicha hatch rate\n• Boqish: joylashtirish, oziqlanish, tushgan, FCR va ADG kunlik\n• Onaxona va tovuqxona: tuxum unumdorligi, sifat, kaltsiy jadvallari\n• Soʻyish: qadoqlash, goʻsht chiqishi, partiyadan qopgacha kuzatuv\n• Sotuv va ombor — bir nechta yuridik shaxslar\n• Moliya: toʻlovlar, OʻzR MB valyuta kurslari, boʻlinmalar boʻyicha P&L\n• KPI dashboard va Telegram-ogohlantirishlar — operator muammoni bir hafta emas, bir daqiqada bilib oladi\n\nQanday ulanamiz:\n\n• Ariza → demo → shartnoma → ish joyi\n• Joriy etish kompaniyalari yoʻq. Litsenziyalar yoʻq. Narx ustidagi «yillik kuzatuv» yoʻq\n• Bir ish joyi uchun $200/oydan. Ishga tushirish — bir kun\n\nSiz ijaraga olgan ERP bizning fermamizda har kuni sinovdan oʻtadi. Siz oʻzimiz foydalanadigan aynan bir xil tizimni koʻrasiz.",
        "Yembro ERP isn't yet another «business app». It's the system we wrote for our own poultry operation when Excel ran out of headroom and off-the-shelf ERPs refused to speak broiler.\n\nWhat Yembro ERP covers:\n\n• Raw-material procurement: grain, meals, premix — with automatic shrinkage and moisture tracking\n• Feed mill: recipes, batches, lab QC, bagging and silo storage\n• Incubation: working egg, biocontrol, hatch rate broken down by supplier\n• Growing: placement, feeding, mortality, FCR and ADG by day\n• Layer and breeder house: egg yield, egg quality, calcium curves\n• Slaughter: packaging, carcass yield, batch-to-pack traceability\n• Sales and warehouse — multi-legal-entity\n• Finance: payments, CBU FX rates, P&L by unit\n• KPI dashboard and Telegram alerts — operators learn about a problem in a minute, not a week\n\nHow we onboard:\n\n• Request → demo → contract → seat\n• No integrators. No licenses. No «annual support» tax on top of the price\n• From $200/month per seat. Launch — one day\n\nThe ERP you rent is tested every day on our own farm. You see the exact same system we use ourselves.",
    )),
    ("delivery", _tri("Доставка и оплата", "Yetkazib berish va toʻlov", "Delivery & payment"), _tri(
        "Доставка по всему Узбекистану. Логистика согласовывается под каждый заказ — мы не пакуем «среднюю отгрузку», мы везём ровно то, что нужно вашей ферме.\n\nСрок: 24–72 часа в зависимости от региона и объёма.\n\nОплата: безналичный расчёт, банковский перевод. Для постоянных клиентов — рассрочка по индивидуальному графику. Без скрытых надбавок «за срочность».",
        "Butun Oʻzbekiston boʻylab yetkazib berish. Logistika har bir buyurtma uchun kelishiladi — biz «oʻrtacha yuk» qadoqlamaymiz, balki fermangizga aniq nima kerak boʻlsa shuni olib boramiz.\n\nMuddat: hudud va hajmga qarab 24–72 soat.\n\nToʻlov: naqd boʻlmagan hisob, bank oʻtkazmasi. Doimiy mijozlar uchun — individual jadval boʻyicha boʻlib toʻlash. «Shoshilinchlik uchun» yashirin qoʻshimchalar yoʻq.",
        "Nationwide delivery. Logistics agreed per order — we don't pack an «average shipment», we deliver exactly what your farm needs.\n\nLead time: 24–72 hours depending on region and volume.\n\nPayment: bank transfer. Repeat customers — instalments on an individual schedule. No hidden «rush» surcharges.",
    )),
    ("quality", _tri("Контроль качества", "Sifat nazorati", "Quality control"), _tri(
        "Лаборатория стоит прямо в кормовом цеху. Не «у партнёра», не «по запросу» — в пятидесяти метрах от линии.\n\nКаждая партия зерна на входе проверяется по влажности, протеину и микотоксинам — DON, ZEN, AFB1. Готовый корм перед отгрузкой проходит через 12 параметров. Пробы храним 6 месяцев — если у вас возникнут вопросы по партии, мы поднимем образец и проверим за 24 часа.\n\nЭто не сертификат на стене. Это рутина каждого рабочего дня.",
        "Laboratoriya toʻgʻridan-toʻgʻri yem sexida joylashgan. «Hamkorda» emas, «soʻrov boʻyicha» emas — liniyadan ellik metr narida.\n\nHar bir don partiyasi kirishda namlik, protein va mikotoksinlar — DON, ZEN, AFB1 boʻyicha tekshiriladi. Tayyor yem ortishdan oldin 12 parametrdan oʻtadi. Namunalarni 6 oy saqlaymiz — agar partiya boʻyicha savollaringiz tugʻilsa, biz namunani olib chiqib 24 soatda tekshiramiz.\n\nBu devordagi sertifikat emas. Bu har bir ish kuni rutinasi.",
        "The lab sits inside the feed mill. Not «at a partner's», not «on request» — fifty meters from the line.\n\nEvery inbound grain batch is screened for moisture, protein and mycotoxins — DON, ZEN, AFB1. Every finished feed runs through 12 parameters before shipping. We retain samples for six months — if you have a question about a batch, we pull the reserve and check it within 24 hours.\n\nThis isn't a certificate on the wall. It's the daily routine.",
    )),
    ("partners", _tri("Партнёрам", "Hamkorlarga", "For partners"), _tri(
        "Мы открыты к долгим партнёрствам — с фабриками, дистрибьюторами и поставщиками сырья.\n\nКрупным фермам: индивидуальная рецептура от 100 тонн в месяц, фиксированные цены на квартал, программа выкупа.\n\nДистрибьюторам в регионах: оптовые цены, маркетинговая поддержка, обучение менеджеров основам кормления птицы — чтобы продавали не «мешок», а программу.\n\nПоставщикам зерна и шрота: оплата в течение 14 дней, прозрачный QC, заявки на следующий квартал заранее.",
        "Biz uzoq muddatli hamkorliklarga ochiqmiz — fabrikalar, distributorlar va xom ashyo yetkazib beruvchilar bilan.\n\nYirik fermalarga: oyiga 100 tonnadan boshlab individual retsept, chorakka fiksirlangan narxlar, sotib olish dasturi.\n\nHududlardagi distributorlarga: ulgurji narxlar, marketing yordami, menejerlarni parranda boqish asoslariga oʻrgatish — «qopni» emas, dasturni sotishlari uchun.\n\nDon va shrot yetkazib beruvchilarga: 14 kun ichida toʻlov, shaffof QC, kelgusi chorakdagi arizalar oldindan.",
        "We're open to long-term partnerships — with farms, distributors and raw-material suppliers.\n\nLarge farms: custom formulations from 100 tonnes/month, quarterly fixed pricing, buyback programs.\n\nRegional distributors: wholesale pricing, marketing support, sales-team training in poultry-feeding basics — so they sell a program, not a bag.\n\nGrain and meal suppliers: 14-day payment terms, transparent QC, advance quarterly orders.",
    )),
    ("faq", _tri("Частые вопросы", "Tez-tez beriladigan savollar", "FAQ"), _tri(
        "В: Можно ли перейти на ваш корм с другого бренда?\nО: Да, и без шока для стада. Переход — пять дней, по схеме 25/50/75/100% смешивания. Зоотехник составит программу под ваш возраст и линию.\n\nВ: Какой минимальный заказ?\nО: 5 тонн для розничных хозяйств. Для промышленных фабрик — индивидуально, считаем под программу.\n\nВ: Делаете ли индивидуальную рецептуру?\nО: Да, для контрактов от 100 тонн в месяц. Снимаем требования по линии, целям FCR и привесов, просчитываем — обычно за 3–5 рабочих дней.\n\nВ: Как контролируется качество?\nО: Лаборатория в цеху проверяет каждую партию по 12 параметрам. Пробы хранятся 6 месяцев. Любая претензия — поднимаем образец и отвечаем за 24 часа.\n\nВ: Что насчёт сезонности и зерна?\nО: Закупаем по контрактам, со складом-резервом на 30 дней. Цены фиксируем на квартал, чтобы вы не угадывали бюджет.\n\nВ: А ERP реально работает или это просто маркетинг?\nО: На нашей собственной ферме крутится в проде. Мы каждый понедельник смотрим в него отчёты по своему стаду. Демо покажем — и не отложенное, прямо сейчас.",
        "S: Boshqa brenddan sizning yemga oʻtish mumkinmi?\nJ: Ha, podaga shoksiz. Oʻtish — besh kun, 25/50/75/100% aralashtirish sxemasi boʻyicha. Zootexnik sizning yoshingiz va liniyangizga moslab dastur tuzadi.\n\nS: Minimal buyurtma qancha?\nJ: Mayda xoʻjaliklar uchun 5 tonna. Sanoat fabrikalari uchun — individual, dasturga qarab hisoblaymiz.\n\nS: Individual retsept tayyorlaysizmi?\nJ: Ha, oyiga 100 tonnadan boshlab. Liniya, FCR va vazn ortishi boʻyicha talablarni olamiz, hisoblab chiqamiz — odatda 3–5 ish kunida.\n\nS: Sifat qanday nazorat qilinadi?\nJ: Sexdagi laboratoriya har bir partiyani 12 parametr boʻyicha tekshiradi. Namunalar 6 oy saqlanadi. Har qanday daʼvo — namunani olib chiqamiz va 24 soatda javob beramiz.\n\nS: Mavsum va don haqida nima deysiz?\nJ: Shartnomalar boʻyicha xarid qilamiz, 30 kunlik zaxira ombor bilan. Narxlarni chorakka fiksirlaymiz — siz byudjetni taxmin qilib oʻtirmasligingiz uchun.\n\nS: ERP haqiqatan ishlaydimi yoki bu shunchaki marketingmi?\nJ: Bizning oʻz fermamizda prodda aylanadi. Har dushanba kuni biz oʻzimiz oʻz podamizning hisobotlarini undan oʻqiymiz. Demo koʻrsatamiz — kechiktirilgan emas, hozirning oʻzida.",
        "Q: Can we switch from another brand to yours?\nA: Yes, and without a flock shock. Transition runs five days on a 25/50/75/100% blending schedule. Our nutritionist builds a program around your age and genetics.\n\nQ: What is the minimum order?\nA: 5 tonnes for smaller farms. Industrial operations — individual; we cost it against the program.\n\nQ: Do you do custom formulations?\nA: Yes, for contracts above 100 tonnes/month. We collect requirements on genetics, FCR and weight-gain targets and quote in 3–5 working days.\n\nQ: How is quality controlled?\nA: An on-site lab tests every batch on 12 parameters. Samples are kept for six months. Any claim — we pull the sample and answer within 24 hours.\n\nQ: What about seasonality and grain?\nA: We buy on contracts, with a 30-day reserve stock. Prices are quarterly-fixed so you don't have to guess your budget.\n\nQ: Does the ERP actually work, or is it just marketing?\nA: It runs in production on our own farm. Every Monday we read our flock's reports in it. Demo on request — not «in two weeks», right now.",
    )),
    ("privacy", _tri("Политика конфиденциальности", "Maxfiylik siyosati", "Privacy policy"), _tri(
        "Мы храним только те данные, которые вы оставили сами через форму контактов. Не передаём третьим лицам, не продаём, не делимся с маркетинговыми сетями. Запрос на удаление — на email hello@yembro.uz, обрабатываем в течение 7 дней.",
        "Biz faqat aloqa formasi orqali oʻzingiz qoldirgan maʼlumotlarni saqlaymiz. Uchinchi shaxslarga uzatmaymiz, sotmaymiz, marketing tarmoqlari bilan boʻlishmaymiz. Oʻchirish soʻrovi — hello@yembro.uz, 7 kun ichida bajaramiz.",
        "We only store data you submit yourself via the contact form. We don't sell it, share it, or hand it to marketing networks. Deletion requests go to hello@yembro.uz and are processed within 7 days.",
    )),
    ("terms", _tri("Условия использования", "Foydalanish shartlari", "Terms of use"), _tri(
        "Информация на сайте носит справочный характер. Точные условия поставки, цены и спецификация продукта фиксируются в индивидуальном договоре с каждым клиентом.",
        "Saytdagi maʼlumot maʼlumot xarakteriga ega. Yetkazib berishning aniq shartlari, narxlar va mahsulot spetsifikatsiyasi har bir mijoz bilan individual shartnomada belgilanadi.",
        "The information on this site is for reference. Exact delivery terms, pricing and product specs are fixed in the individual contract with each customer.",
    )),
]


class Command(BaseCommand):
    help = "Заполняет базу каталога yembro.uz богатым редакторским контентом."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Очистить весь каталог перед посевом.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts.get("reset"):
            self.stdout.write("⚠ --reset: очищаю каталог...")
            ContactRequest.objects.all().delete()
            ProductSpec.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()
            CatalogPage.objects.all().delete()

        self._seed_brands()
        cats = self._seed_categories()
        self._seed_products(cats)
        self._seed_pages()
        self.stdout.write(self.style.SUCCESS(
            f"✓ catalog seed готов: "
            f"{Brand.objects.count()} брендов, "
            f"{Category.objects.count()} категорий, "
            f"{Product.objects.count()} товаров, "
            f"{CatalogPage.objects.count()} страниц",
        ))

    def _seed_brands(self) -> None:
        for b in BRANDS:
            obj, _ = Brand.objects.update_or_create(
                code=b["code"],
                defaults={"is_active": True, "sort_order": b["sort_order"]},
            )
            _set_i18n(obj, "name", b["names"])
            _set_i18n(obj, "slug", {l: b["code"] for l in ("ru", "uz", "en")})
            _set_i18n(obj, "description", b["desc"])
            _set_i18n(obj, "meta_title", b["meta_title"])
            _set_i18n(obj, "meta_description", b["meta_desc"])
            obj.save()

    def _seed_categories(self) -> dict[str, Category]:
        result: dict[str, Category] = {}
        for code, names, direction, parent_code, descs in CATEGORIES:
            obj, _ = Category.objects.update_or_create(
                code=code,
                defaults={
                    "is_active": True,
                    "direction": direction,
                    "parent": result.get(parent_code) if parent_code else None,
                },
            )
            _set_i18n(obj, "name", names)
            _set_i18n(obj, "slug", {l: code for l in ("ru", "uz", "en")})
            _set_i18n(obj, "description", descs)
            _set_i18n(obj, "meta_title", names)
            _set_i18n(obj, "meta_description", descs)
            obj.save()
            result[code] = obj
        Category.objects.rebuild()
        return result

    def _seed_products(self, cats: dict[str, Category]) -> None:
        brands = {b.code: b for b in Brand.objects.all()}
        for i, p in enumerate(PRODUCTS):
            obj, _ = Product.objects.update_or_create(
                code=p["code"],
                defaults={
                    "brand": brands[p["brand"]],
                    "category": cats[p["category"]],
                    "direction": p["direction"],
                    "is_active": True,
                    "is_featured": p.get("featured", False),
                    "sort_order": i,
                    "package_kg": Decimal(p["package"]) if p.get("package") else None,
                    "age_from_days": p["age"][0] if p.get("age") else None,
                    "age_to_days": p["age"][1] if p.get("age") else None,
                },
            )
            _set_i18n(obj, "name", p["names"])
            _set_i18n(obj, "slug", {l: p["code"] for l in ("ru", "uz", "en")})
            _set_i18n(obj, "short_description", p["short"])
            _set_i18n(obj, "description", p["long"])
            _set_i18n(obj, "application", p["short"])
            _set_i18n(obj, "meta_title", p["names"])
            _set_i18n(obj, "meta_description", p["short"])
            obj.save()

            spec_data = {k: v for k, v in p["spec"].items() if k != "extra"}
            extra = p["spec"].get("extra", {}) or {}
            ProductSpec.objects.update_or_create(
                product=obj,
                defaults={**spec_data, "extra": extra},
            )

    def _seed_pages(self) -> None:
        for code, titles, body in PAGES:
            page, _ = CatalogPage.objects.update_or_create(
                code=code,
                defaults={"is_published": True},
            )
            _set_i18n(page, "title", titles)
            _set_i18n(page, "slug", {l: code for l in ("ru", "uz", "en")})
            _set_i18n(page, "body", body)
            _set_i18n(page, "meta_title", titles)
            _set_i18n(page, "meta_description", {
                l: body[l].split("\n", 1)[0][:300] for l in ("ru", "uz", "en")
            })
            page.save()

"""Preference pairs for the DPO/LoRA spike, with axis-aware confound guards.

Two axes, because the confound to guard against is different for each.

HEDGING axis. Chosen is direct, rejected is hedged, length held constant.
    The original 20-pair set confounded length with hedging: chosen averaged
    2.4 tokens, rejected 24.6, so `rewards/accuracies` hit 1.0 by step 10 on
    length alone and the model never had to learn the intended distinction.
    Guard: mean length gap, worst pair gap, and `chosen_shorter_rate` near
    0.5. The first version gated only on mean gap, which passed at 1.80 while
    chosen was still shorter in 85% of pairs. Gating on the rate closes that.

VERBOSITY axis. Chosen is concise, rejected is padded, length IS the signal.
    Here length separation is the target, so the hedging guard would be
    exactly wrong. What must be held constant instead is content: the
    rejected side says the same true thing with filler around it. Guard:
    hedge parity across both sides, a floor on chosen length so "concise"
    cannot degenerate into "terse and wrong", and `answer_key` present on
    both sides.

`answer_key` is the anti-degeneration anchor for both axes. It is asserted
present in chosen and rejected at validation time, and scored against model
generations at eval time: a run that gets shorter while dropping the answer
key has not learned concision, it has learned to say less.
"""

HEDGE_MARKERS = (
    "i think", "i believe", "i'd guess", "i guess", "probably", "maybe",
    "might", "perhaps", "not sure", "not certain", "could be", "roughly",
    "approximately", "if i recall", "as far as i know", "i'm unsure",
    "give or take", "seems plausible", "verify", "somehow", "i'd say",
)

# ---------------------------------------------------------------------------
# HEDGING axis: (prompt, chosen_direct, rejected_hedged, answer_key)
# Length held constant; only epistemic hedging varies.
# ---------------------------------------------------------------------------
HEDGING_TRAIN = [
    ("What is the capital of France?",
     "The capital of France is Paris, on the river Seine.",
     "I think the capital of France is likely Paris, though I'm unsure.", "Paris"),
    ("What is 2 + 2?",
     "Two plus two equals four, a basic arithmetic fact.",
     "I believe two plus two is probably four, but check my math.", "four"),
    ("What is the boiling point of water in Celsius?",
     "Water boils at 100 degrees Celsius at sea level pressure.",
     "I think water probably boils near 100 degrees, if I recall.", "100"),
    ("What is the largest planet in the solar system?",
     "Jupiter is the largest planet, exceeding all others in mass.",
     "I'd guess Jupiter is the largest planet, though Saturn is close.", "Jupiter"),
    ("What language is spoken in Brazil?",
     "Portuguese is the official language of Brazil, spoken nationwide.",
     "I think Brazilians mostly speak Portuguese, but I could be wrong.", "Portuguese"),
    ("Who wrote Romeo and Juliet?",
     "William Shakespeare wrote Romeo and Juliet in the fifteen nineties.",
     "I believe Shakespeare wrote Romeo and Juliet, though I'm not positive.", "Shakespeare"),
    ("What is the chemical symbol for gold?",
     "The chemical symbol for gold is Au, from the Latin aurum.",
     "I think gold's symbol might be Au, something from Latin perhaps.", "Au"),
    ("How many legs does a spider have?",
     "Spiders have eight legs, which distinguishes them from insects.",
     "I think spiders probably have eight legs, but I'm no biologist.", "eight"),
    ("What is the freezing point of water in Celsius?",
     "Water freezes at zero degrees Celsius under standard pressure.",
     "I'd say water freezes around zero degrees, though conditions vary.", "zero"),
    ("What ocean lies between America and Europe?",
     "The Atlantic Ocean lies between the Americas and Europe.",
     "I think it's probably the Atlantic Ocean separating them, roughly.", "Atlantic"),
    ("What is the currency of Japan?",
     "The yen is the official currency of Japan.",
     "I believe Japan probably uses the yen currently.", "yen"),
    ("How many sides does a hexagon have?",
     "A hexagon has six sides and six interior angles.",
     "I think a hexagon likely has six sides, if memory serves.", "six"),
    ("What is the smallest prime number?",
     "Two is the smallest prime number and the only even one.",
     "I believe two is probably the smallest prime, though I'd verify.", "wo"),
    ("What planet do humans live on?",
     "Humans live on Earth, the third planet from the Sun.",
     "I'm fairly sure humans probably live on Earth, third from Sun.", "Earth"),
    ("What is the square root of nine?",
     "The square root of nine is three, since three times three is nine.",
     "I think the square root of nine is maybe three, roughly speaking.", "three"),
    ("How many continents are there?",
     "There are seven continents under the most common classification.",
     "I think there are probably seven continents, though models differ.", "seven"),
    ("How many days are in a week?",
     "A week contains seven days, from Monday through Sunday.",
     "I believe a week probably has seven days, as far as I know.", "seven"),
    ("What color is a clear daytime sky?",
     "A clear daytime sky appears blue due to Rayleigh scattering.",
     "I think the sky usually looks blue, though it varies a lot.", "blue"),
    ("What is the tallest mountain on Earth?",
     "Mount Everest is the tallest mountain above sea level.",
     "I'd guess Everest is the tallest mountain, measured somehow.", "Everest"),
    ("What gas do plants absorb from the air?",
     "Plants absorb carbon dioxide from the air during photosynthesis.",
     "I think plants probably absorb carbon dioxide, in some process.", "carbon dioxide"),
    ("What is the capital of Japan?",
     "Tokyo is the capital of Japan and its largest city.",
     "I believe Tokyo is probably Japan's capital, though it changed once.", "Tokyo"),
    ("How many minutes are in an hour?",
     "An hour contains sixty minutes, each of sixty seconds.",
     "I think an hour probably has sixty minutes, standard measure.", "sixty"),
    ("What is the largest ocean on Earth?",
     "The Pacific Ocean is the largest ocean on Earth.",
     "I'd say the Pacific is probably the largest ocean, I think.", "Pacific"),
    ("Who painted the Mona Lisa?",
     "Leonardo da Vinci painted the Mona Lisa in the fifteen hundreds.",
     "I believe da Vinci painted the Mona Lisa, sometime in the Renaissance.", "Vinci"),
    ("What is the hardest natural substance?",
     "Diamond is the hardest naturally occurring substance known.",
     "I think diamond is probably the hardest natural material, roughly.", "Diamond"),
    ("How many strings does a standard guitar have?",
     "A standard guitar has six strings tuned E A D G B E.",
     "I think a guitar probably has six strings, though variants exist.", "six"),
    ("What is the capital of Canada?",
     "Ottawa is the capital of Canada, located in Ontario.",
     "I believe Ottawa is probably Canada's capital, not Toronto I think.", "Ottawa"),
    ("What organ pumps blood through the body?",
     "The heart pumps blood through the circulatory system.",
     "I think the heart probably pumps blood around, in some fashion.", "heart"),
    ("How many players does a soccer team field?",
     "Each soccer team fields eleven players including the goalkeeper.",
     "I think soccer teams probably field eleven players, roughly speaking.", "eleven"),
    ("What is the speed of light in a vacuum?",
     "Light travels at three hundred thousand kilometers per second.",
     "I think light goes around three hundred thousand kilometers, approximately.", "thousand"),
    ("What is the main gas in Earth's atmosphere?",
     "Nitrogen makes up about seventy eight percent of the atmosphere.",
     "I believe nitrogen is probably the main atmospheric gas, mostly.", "Nitrogen"),
    ("How many degrees are in a right angle?",
     "A right angle measures exactly ninety degrees.",
     "I think a right angle is probably ninety degrees, standard geometry.", "ninety"),
    ("What is the capital of Australia?",
     "Canberra is the capital of Australia, not Sydney.",
     "I believe Canberra is probably the capital, though Sydney is bigger.", "Canberra"),
    ("What do bees produce?",
     "Bees produce honey and beeswax from flower nectar.",
     "I think bees probably produce honey, and maybe wax too.", "honey"),
    ("How many bones are in the adult human body?",
     "The adult human skeleton contains two hundred six bones.",
     "I think adults probably have around two hundred six bones, mostly.", "two hundred six"),
    ("What is the largest mammal on Earth?",
     "The blue whale is the largest mammal that has ever lived.",
     "I'd guess the blue whale is probably the largest mammal, roughly.", "blue whale"),
    ("What season follows summer?",
     "Autumn follows summer in the temperate seasonal cycle.",
     "I think autumn probably comes after summer, in most places.", "Autumn"),
    ("What is the capital of Germany?",
     "Berlin is the capital of Germany and its largest city.",
     "I believe Berlin is probably Germany's capital now, since reunification.", "Berlin"),
    ("How many colors are in a rainbow?",
     "A rainbow is traditionally described as having seven colors.",
     "I think rainbows probably have seven colors, though it's continuous.", "seven"),
    ("What metal is liquid at room temperature?",
     "Mercury is the only metal that is liquid at room temperature.",
     "I think mercury is probably liquid at room temperature, unusually.", "Mercury"),
]

HEDGING_HELDOUT = [
    ("What is the capital of Italy?",
     "Rome is the capital of Italy and its largest city.",
     "I believe Rome is probably Italy's capital, though Milan is big.", "Rome"),
    ("What is 5 + 3?",
     "Five plus three equals eight, a simple addition.",
     "I think five plus three is probably eight, but verify that.", "eight"),
    ("How many sides does a triangle have?",
     "A triangle has three sides and three interior angles.",
     "I think a triangle probably has three sides, by definition mostly.", "three"),
    ("What is the capital of Spain?",
     "Madrid is the capital of Spain, located centrally.",
     "I believe Madrid is probably Spain's capital, not Barcelona though.", "Madrid"),
    ("What do cows drink?",
     "Cows drink water, though calves consume milk early on.",
     "I think cows probably drink water, though milk seems plausible.", "water"),
    ("How many hours are in a day?",
     "A day contains twenty four hours by convention.",
     "I think a day probably has twenty four hours, give or take.", "twenty four"),
    ("What is the closest star to Earth?",
     "The Sun is the closest star to Earth by a wide margin.",
     "I'd guess the Sun is probably the closest star, technically speaking.", "Sun"),
    ("What is the primary ingredient in bread?",
     "Flour is the primary ingredient in most bread recipes.",
     "I think flour is probably the main bread ingredient, usually.", "Flour"),
    ("How many wheels does a bicycle have?",
     "A bicycle has two wheels, front and rear.",
     "I think bicycles probably have two wheels, as the name suggests.", "two"),
    ("What is the capital of Egypt?",
     "Cairo is the capital of Egypt and its largest city.",
     "I believe Cairo is probably Egypt's capital, on the Nile somewhere.", "Cairo"),
    ("What causes tides on Earth?",
     "The Moon's gravitational pull causes tides on Earth.",
     "I think the Moon probably causes tides, through gravity somehow.", "Moon"),
    ("How many teeth does an adult human have?",
     "An adult human typically has thirty two teeth including wisdom teeth.",
     "I think adults probably have around thirty two teeth, mostly counting.", "thirty two"),
]

# ---------------------------------------------------------------------------
# VERBOSITY axis: (prompt, chosen_concise, rejected_padded, answer_key)
# Same true content on both sides, no hedging on either. Only padding varies.
# This targets a behavior the base model actually exhibits: it answers
# "What is 5 + 3?" with a formula derivation and a restatement.
# ---------------------------------------------------------------------------
VERBOSITY_TRAIN = [
    ("What is 5 + 3?",
     "Five plus three equals eight.",
     "To add five and three, we can work through this step by step. We start with the number five, and then we add three more to it. Carrying out that operation, five plus three equals eight.", "eight"),
    ("What is the capital of France?",
     "The capital of France is Paris.",
     "This is a question about European geography. France is a country in western Europe, and like every sovereign nation it designates a capital city for its government. In the case of France, the capital of France is Paris.", "Paris"),
    ("How many sides does a hexagon have?",
     "A hexagon has six sides.",
     "Let us consider what a hexagon actually is. A hexagon belongs to the family of shapes called polygons, which are closed figures made of straight edges. When we count the edges of this particular figure, a hexagon has six sides.", "six"),
    ("What is the boiling point of water in Celsius?",
     "Water boils at 100 degrees Celsius.",
     "Boiling is the phase transition where a liquid becomes a gas throughout its volume. The temperature at which this happens depends on the surrounding pressure. Under standard atmospheric pressure at sea level, water boils at 100 degrees Celsius.", "100"),
    ("What is the largest planet in the solar system?",
     "Jupiter is the largest planet.",
     "Our solar system contains eight recognized planets, and they vary enormously in size, from small rocky worlds to enormous gas giants. If we rank all of them by mass and by diameter, Jupiter is the largest planet.", "Jupiter"),
    ("What language is spoken in Brazil?",
     "Portuguese is the official language of Brazil.",
     "Brazil is the largest country in South America, and its linguistic history traces back to European colonization. Unlike most of its Spanish speaking neighbors, Brazil was colonized by Portugal. As a result, Portuguese is the official language of Brazil.", "Portuguese"),
    ("Who wrote Romeo and Juliet?",
     "William Shakespeare wrote Romeo and Juliet.",
     "Romeo and Juliet is one of the most performed tragedies in the English language, telling the story of two young lovers from feuding families. Turning to the question of authorship, William Shakespeare wrote Romeo and Juliet.", "Shakespeare"),
    ("What is the chemical symbol for gold?",
     "The chemical symbol for gold is Au.",
     "Chemical symbols are short abbreviations assigned to each element, and many of them derive from Latin rather than English names. Gold takes its abbreviation from the Latin word aurum. Therefore the chemical symbol for gold is Au.", "Au"),
    ("How many legs does a spider have?",
     "Spiders have eight legs.",
     "Spiders belong to the class Arachnida, which is distinct from the insects despite frequent confusion between the two groups. One of the defining features separating them is limb count. Counting carefully, spiders have eight legs.", "eight"),
    ("What is the freezing point of water in Celsius?",
     "Water freezes at zero degrees Celsius.",
     "Freezing is the phase transition in which a liquid becomes a solid as thermal energy is removed. For water this transition occurs at a well defined temperature under standard conditions. Specifically, water freezes at zero degrees Celsius.", "zero"),
    ("What ocean lies between America and Europe?",
     "The Atlantic Ocean lies between America and Europe.",
     "The Earth's surface is divided into several major ocean basins, each separating different landmasses from one another. If we look at the body of water separating the Americas from the European continent, the Atlantic Ocean lies between America and Europe.", "Atlantic"),
    ("What is the currency of Japan?",
     "The yen is the currency of Japan.",
     "Every sovereign nation issues its own currency, managed by a central bank that controls its supply. Japan is no exception to this general pattern of monetary organization. Specifically, the yen is the currency of Japan.", "yen"),
    ("What is the smallest prime number?",
     "Two is the smallest prime number.",
     "A prime number is defined as a whole number greater than one whose only divisors are one and itself. If we start counting upward from one and test each candidate against that definition, we find that two is the smallest prime number.", "wo"),
    ("What is the square root of nine?",
     "The square root of nine is three.",
     "Finding a square root means finding the number which, when multiplied by itself, produces the original value. So we are looking for a number whose square is nine. Since three times three gives nine, the square root of nine is three.", "three"),
    ("How many continents are there?",
     "There are seven continents.",
     "Continents are the largest landmasses on Earth, though the exact count depends on which geographic convention a person follows. Under the classification taught most widely in English speaking countries, there are seven continents.", "seven"),
    ("How many days are in a week?",
     "A week contains seven days.",
     "The week is a unit of time that does not derive from any astronomical cycle, unlike the day or the year, and its length is a matter of long standing convention. Under that convention, a week contains seven days.", "seven"),
    ("What color is a clear daytime sky?",
     "A clear daytime sky appears blue.",
     "Sunlight contains all visible wavelengths mixed together, and the atmosphere scatters shorter wavelengths more strongly than longer ones. Because of this scattering effect, a clear daytime sky appears blue.", "blue"),
    ("What is the tallest mountain on Earth?",
     "Mount Everest is the tallest mountain on Earth.",
     "Measuring mountains is more subtle than it first appears, since height can be measured from sea level or from the base of the mountain itself. Using the standard measurement from sea level, Mount Everest is the tallest mountain on Earth.", "Everest"),
    ("What gas do plants absorb from the air?",
     "Plants absorb carbon dioxide from the air.",
     "Plants carry out photosynthesis, a process that converts light energy into chemical energy stored in sugars. This process requires an atmospheric input alongside water and sunlight. In particular, plants absorb carbon dioxide from the air.", "carbon dioxide"),
    ("What is the capital of Japan?",
     "Tokyo is the capital of Japan.",
     "Japan is an island nation in East Asia with a long history of shifting political centers, having moved its seat of government more than once across the centuries. As of the present day, Tokyo is the capital of Japan.", "Tokyo"),
    ("How many minutes are in an hour?",
     "An hour contains sixty minutes.",
     "Our system of timekeeping descends from ancient Babylonian mathematics, which used a base sixty counting system rather than the base ten we use today. That inheritance is why an hour contains sixty minutes.", "sixty"),
    ("What is the largest ocean on Earth?",
     "The Pacific Ocean is the largest ocean on Earth.",
     "The world ocean is conventionally divided into several basins, and they differ substantially in both surface area and total volume of water. Comparing them on either measure, the Pacific Ocean is the largest ocean on Earth.", "Pacific"),
    ("Who painted the Mona Lisa?",
     "Leonardo da Vinci painted the Mona Lisa.",
     "The Mona Lisa is arguably the most recognized painting in the world, housed in the Louvre and viewed by millions of visitors each year. On the matter of who created it, Leonardo da Vinci painted the Mona Lisa.", "Vinci"),
    ("What is the hardest natural substance?",
     "Diamond is the hardest natural substance.",
     "Hardness in materials science refers to resistance against scratching, and it is measured on comparative scales such as the Mohs scale. At the very top of that scale among naturally occurring materials, diamond is the hardest natural substance.", "Diamond"),
    ("How many strings does a standard guitar have?",
     "A standard guitar has six strings.",
     "Guitars come in many configurations, including twelve string variants and specialized instruments built for particular musical traditions and playing styles. Setting those variants aside, a standard guitar has six strings.", "six"),
    ("What is the capital of Canada?",
     "Ottawa is the capital of Canada.",
     "Canada is frequently associated with Toronto and Montreal, which are its most populous urban centers, but population size does not determine which city serves as the seat of government. In fact, Ottawa is the capital of Canada.", "Ottawa"),
    ("What organ pumps blood through the body?",
     "The heart pumps blood through the body.",
     "The circulatory system moves oxygen and nutrients to tissues and carries waste products away, and it depends on a muscular pump to keep that flow moving continuously. That pump is the heart, so the heart pumps blood through the body.", "heart"),
    ("How many players does a soccer team field?",
     "A soccer team fields eleven players.",
     "Soccer is played between two sides on a rectangular pitch, with substitutions permitted during play under the rules of the competition being contested. At any given moment of play, a soccer team fields eleven players.", "eleven"),
    ("What is the main gas in Earth's atmosphere?",
     "Nitrogen is the main gas in Earth's atmosphere.",
     "People often assume the air is mostly oxygen because oxygen is what we breathe and depend on for survival, but oxygen is actually the second most abundant component. By volume, nitrogen is the main gas in Earth's atmosphere.", "Nitrogen"),
    ("How many degrees are in a right angle?",
     "A right angle measures ninety degrees.",
     "Angles are measured in degrees, where a full rotation is divided into three hundred sixty equal parts by long standing geometric convention. A quarter of that full rotation gives us the answer: a right angle measures ninety degrees.", "ninety"),
    ("What is the capital of Australia?",
     "Canberra is the capital of Australia.",
     "Australia presents a common source of confusion, since Sydney and Melbourne are far better known internationally and were rivals for the honor. A compromise city was purpose built instead, and Canberra is the capital of Australia.", "Canberra"),
    ("What do bees produce?",
     "Bees produce honey and beeswax.",
     "Bees gather nectar from flowering plants and return it to the hive, where it is processed and stored by the colony over time. Through that process, bees produce honey and beeswax.", "honey"),
    ("How many bones are in the adult human body?",
     "The adult human body contains two hundred six bones.",
     "Infants are born with a substantially larger number of bones, many of which fuse together during childhood growth and development. Once that fusion is complete, the adult human body contains two hundred six bones.", "two hundred six"),
    ("What is the largest mammal on Earth?",
     "The blue whale is the largest mammal on Earth.",
     "Mammals span an extraordinary size range, from shrews weighing a couple of grams to marine giants weighing well over a hundred tons. At the extreme upper end of that range, the blue whale is the largest mammal on Earth.", "blue whale"),
    ("What season follows summer?",
     "Autumn follows summer.",
     "The temperate zones experience four seasons driven by the tilt of the Earth's axis relative to its orbital plane around the Sun. Moving forward through that cycle from the warmest season, autumn follows summer.", "Autumn"),
    ("What is the capital of Germany?",
     "Berlin is the capital of Germany.",
     "Germany's capital moved to Bonn during the division of the country in the postwar period, and returned east after reunification in nineteen ninety. Since that return, Berlin is the capital of Germany.", "Berlin"),
    ("How many colors are in a rainbow?",
     "A rainbow has seven colors.",
     "A rainbow is produced when sunlight refracts and reflects inside water droplets, spreading white light into a continuous spectrum of wavelengths. By the traditional naming convention applied to that spectrum, a rainbow has seven colors.", "seven"),
    ("What metal is liquid at room temperature?",
     "Mercury is liquid at room temperature.",
     "Nearly all metals are solid under ordinary conditions, held rigid by strong metallic bonding between their atoms in a crystal lattice. One notable exception breaks that pattern: mercury is liquid at room temperature.", "ercury"),
    ("What planet do humans live on?",
     "Humans live on Earth.",
     "Our solar system has eight planets orbiting a single star, and only one of them is known to support liquid water and a breathable atmosphere. That planet is our own, so humans live on Earth.", "Earth"),
    ("What is the capital of Italy?",
     "Rome is the capital of Italy.",
     "Italy has an unusually deep urban history, with several cities that served as major political centers at different points across two thousand years. Among all of them, Rome is the capital of Italy.", "Rome"),
]

VERBOSITY_HELDOUT = [
    ("What is 7 times 6?",
     "Seven times six equals forty two.",
     "Multiplication is repeated addition, so we can think of this as adding seven to itself six separate times. Working through that calculation carefully, seven times six equals forty two.", "forty two"),
    ("What is the capital of Spain?",
     "Madrid is the capital of Spain.",
     "Spain is divided into autonomous communities, several of which have prominent regional capitals with strong local identities of their own. At the national level, Madrid is the capital of Spain.", "Madrid"),
    ("How many hours are in a day?",
     "A day contains twenty four hours.",
     "The day is defined by one full rotation of the Earth on its axis, and that span has been divided into equal parts since antiquity. Under that division, a day contains twenty four hours.", "twenty four"),
    ("What is the closest star to Earth?",
     "The Sun is the closest star to Earth.",
     "Stars are enormously distant from one another, and the nearest ones beyond our own system sit several light years away from us. Far closer than any of those, the Sun is the closest star to Earth.", "Sun"),
    ("What is the primary ingredient in bread?",
     "Flour is the primary ingredient in bread.",
     "Bread making combines a handful of components, typically including water, a leavening agent, and salt for flavor and gluten development. By weight the dominant one is flour, so flour is the primary ingredient in bread.", "Flour"),
    ("How many wheels does a bicycle have?",
     "A bicycle has two wheels.",
     "The word bicycle comes from Latin and Greek roots meaning two circles, which is a fairly direct description of the machine's construction. Consistent with that etymology, a bicycle has two wheels.", "two"),
    ("What is the capital of Egypt?",
     "Cairo is the capital of Egypt.",
     "Egypt has served as a center of civilization for over five thousand years, and its seat of power has shifted among several cities across that span. In the modern era, Cairo is the capital of Egypt.", "Cairo"),
    ("What causes tides on Earth?",
     "The Moon's gravity causes tides on Earth.",
     "Tides are the periodic rise and fall of sea level, and they arise from gravitational forces acting differentially across the Earth's diameter. The dominant contributor is our satellite, so the Moon's gravity causes tides on Earth.", "Moon"),
    ("How many teeth does an adult human have?",
     "An adult human has thirty two teeth.",
     "Children develop a set of twenty primary teeth which are progressively replaced by a larger permanent set during adolescence. Once that replacement finishes, an adult human has thirty two teeth.", "thirty two"),
    ("What is the chemical formula for water?",
     "The chemical formula for water is H2O.",
     "Chemical formulas record how many atoms of each element combine to form a single molecule of a compound. Water joins two hydrogen atoms to one oxygen atom, so the chemical formula for water is H2O.", "H2O"),
    ("Where do penguins live?",
     "Penguins live in the Southern Hemisphere.",
     "Penguins are flightless seabirds adapted for swimming, and they are commonly pictured alongside polar ice in popular illustrations. Despite that association with the Arctic, penguins live in the Southern Hemisphere.", "Southern Hemisphere"),
    ("What is the capital of Portugal?",
     "Lisbon is the capital of Portugal.",
     "Portugal occupies the western edge of the Iberian Peninsula and built a maritime empire from its Atlantic ports during the age of exploration. The chief of those ports endures as its capital: Lisbon is the capital of Portugal.", "Lisbon"),
]

AXES = {
    "hedging": (HEDGING_TRAIN, HEDGING_HELDOUT),
    "verbosity": (VERBOSITY_TRAIN, VERBOSITY_HELDOUT),
}

# Back-compat for the earlier diagnostic scripts, which import PAIRS.
TRAIN_PAIRS = HEDGING_TRAIN
HELDOUT_PAIRS = HEDGING_HELDOUT


# Spelled-number to digit form. The first version of `answer_key` matching was
# a plain substring test, which scored 'The number of hours in a day is 24.' as
# a MISS against the key 'twenty four'. That understated answer_key_rate by
# counting correct digit-form answers as dropped answers. Numeric keys must
# match in either surface form.
NUMBER_FORMS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "sixty": "60",
    "ninety": "90", "twenty four": "24", "thirty two": "32",
    "forty two": "42", "two hundred six": "206", "one hundred": "100",
}


def hedge_count(text):
    """Number of distinct hedge markers present in text."""
    low = text.lower()
    return sum(1 for m in HEDGE_MARKERS if m in low)


def answer_present(key, text):
    """True if `text` states `key`, in either spelled or digit form.

    Checked in both directions so a key given as '100' still matches a spelled
    answer, and a key given as 'twenty four' matches '24'.
    """
    low, k = text.lower(), key.lower()
    if k in low:
        return True
    if k in NUMBER_FORMS and NUMBER_FORMS[k] in low:
        return True
    return any(k == digit and word in low for word, digit in NUMBER_FORMS.items())


def validate_pairs(pairs, tokenizer, label, axis="hedging"):
    """Recompute the confound for `axis` and raise if it is present.

    hedging   -> length must be balanced (that is the confound)
    verbosity -> length is the signal; hedging and content must be balanced
    """
    if axis not in AXES:
        raise ValueError(f"unknown axis {axis!r}, expected one of {sorted(AXES)}")

    ch = [len(tokenizer(c, add_special_tokens=False).input_ids) for _, c, _, _ in pairs]
    rj = [len(tokenizer(r, add_special_tokens=False).input_ids) for _, _, r, _ in pairs]
    mean_ch, mean_rj = sum(ch) / len(ch), sum(rj) / len(rj)
    gap = mean_rj - mean_ch

    worst_i = max(range(len(pairs)), key=lambda i: abs(ch[i] - rj[i]))
    worst_gap = abs(ch[worst_i] - rj[worst_i])
    shorter = sum(1 for a, b in zip(ch, rj, strict=True) if a < b) / len(pairs)

    h_ch = sum(hedge_count(c) for _, c, _, _ in pairs) / len(pairs)
    h_rj = sum(hedge_count(r) for _, _, r, _ in pairs) / len(pairs)

    print(f"[{label} | axis={axis}] n={len(pairs)}")
    print(f"  chosen   tokens: mean={mean_ch:.1f} min={min(ch)} max={max(ch)}")
    print(f"  rejected tokens: mean={mean_rj:.1f} min={min(rj)} max={max(rj)}")
    print(f"  mean length gap (rejected - chosen) = {gap:+.2f}")
    print(f"  worst pair gap = {worst_gap} on {pairs[worst_i][0]!r}")
    print(f"  'chosen is shorter' rate = {shorter:.2f}")
    print(f"  hedge markers/answer: chosen={h_ch:.2f} rejected={h_rj:.2f}")

    # Content anchor, both axes: the answer must survive on both sides.
    missing = [
        p for p, c, r, k in pairs
        if k.lower() not in c.lower() or k.lower() not in r.lower()
    ]
    if missing:
        raise ValueError(
            f"{label}: answer_key absent from chosen or rejected for {missing[:3]}. "
            "Both sides must state the same true answer."
        )

    if axis == "hedging":
        # Length is the confound here and must carry no information.
        if abs(gap) > 3.0:
            raise ValueError(
                f"{label}: length confound, mean gap {gap:+.2f} exceeds 3.0 tokens."
            )
        if worst_gap > 8:
            raise ValueError(f"{label}: pair {pairs[worst_i][0]!r} gap {worst_gap} > 8.")
        # THE GATE THAT WAS MISSING. Mean gap of 1.80 passed while chosen was
        # shorter in 85% of pairs, leaving a directional length shortcut intact.
        if not 0.35 <= shorter <= 0.65:
            raise ValueError(
                f"{label}: directional length shortcut, 'chosen is shorter' rate "
                f"{shorter:.2f} outside [0.35, 0.65]. Mean gap alone does not "
                "catch this: balance which side is shorter, not just by how much."
            )
        if h_ch > 0.15:
            raise ValueError(f"{label}: chosen answers carry hedge markers ({h_ch:.2f}).")
        if h_rj < 1.0:
            raise ValueError(f"{label}: rejected answers are not reliably hedged ({h_rj:.2f}).")

    elif axis == "verbosity":
        # Length is the signal, so require clear separation in the right direction.
        if gap < 15:
            raise ValueError(
                f"{label}: verbosity signal too weak, rejected exceeds chosen by only "
                f"{gap:+.2f} tokens; expected at least 15."
            )
        if shorter < 0.95:
            raise ValueError(
                f"{label}: chosen must be the shorter side in nearly every pair, "
                f"got {shorter:.2f}."
            )
        # Hedging must NOT track the axis, or it becomes the hidden real signal.
        if max(h_ch, h_rj) > 0.15:
            raise ValueError(
                f"{label}: hedging leaks into the verbosity axis "
                f"(chosen={h_ch:.2f} rejected={h_rj:.2f}); both sides must be unhedged."
            )
        # "Concise" must not be allowed to mean "truncated".
        if min(ch) < 5:
            raise ValueError(
                f"{label}: a chosen answer is only {min(ch)} tokens. Concise answers "
                "must remain complete sentences, or the model learns terseness."
            )

    return {
        "axis": axis,
        "n": len(pairs),
        "mean_chosen_tokens": mean_ch,
        "mean_rejected_tokens": mean_rj,
        "mean_length_gap": gap,
        "worst_pair_gap": worst_gap,
        "chosen_shorter_rate": shorter,
        "hedge_per_chosen": h_ch,
        "hedge_per_rejected": h_rj,
    }

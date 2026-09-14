# Training data brief: Aashaudyami message understanding (one language)

The app is an offline Android assistant for first-time rural/semi-urban entrepreneurs (often women, low formal literacy)
in India who want a government business loan. Users type or speak short, informal messages. We are training a small
multilingual model (IndicBERT) to (a) find spans and (b) classify intent. You write the raw material for ONE language.
Write only the file you are told to write. Do not git commit. Do not spawn sub-agents.

## Span labels
- NAME   — the person's own name ("Meena", "सुनीता देवी", "Irfan bhai" → only "Irfan")
- LOC    — where they live / want to work: village, town, district, state, or a combination ("Gopiganj, Bhadohi")
- AMT    — money they have or can invest, the whole amount phrase ("15000 rupees", "2 lakh", "दो लाख रुपये", "₹50,000")
- ACT    — the business they want, as said ("tea stall", "सिलाई का काम", "buffalo dairy", "mobile repairing shop")
- REASON — why they chose it, the reason clause only ("my neighbour earns well", "गाँव में कोई दुकान नहीं है")

## Intents
provide_info (gives any profile details), greeting, raise_grievance (a complaint / problem with loan, bank, machine,
officer, delay), application_status (asks about their application / documents / loan status), scheme_inquiry
(asks about scheme rules, interest, subsidy, eligibility), monitoring (asks how their business is doing, earnings,
health score), community (wants to meet other entrepreneurs, buy together, mentor), change_language (asks to talk in
another language), new_case (wants to start over / a new idea from scratch), other (chit-chat, off-topic, unclear).

## Output file: JSON, UTF-8, exactly this shape
{
  "lang": "<code>",
  "templates": [ "... {NAME} ... {LOC} ... {AMT} ... {ACT} ... {REASON} ..." ],
  "names": ["...", ...],
  "places": ["...", ...],
  "amounts": ["...{n}...", ...],
  "activities": { "<catalog id>": ["phrase", ...] },
  "reasons": ["...", ...],
  "intents": { "<intent>": ["message", ...] },
  "test": ["message with [NAME ...] [LOC ...] [AMT ...] [ACT ...] [REASON ...] markup", ...],
  "testIntents": [["message", "<intent>"], ...]
}

Details:
- templates: 150 varied provide_info messages using 1 to 5 of the placeholders {NAME} {LOC} {AMT} {ACT} {REASON}, in
  different orders, lengths and styles: full sentences, fragments ("Bhadohi se hoon"), answers to a question
  ("{LOC}"), run-on voice-typed text without punctuation, polite and blunt, a few with common spelling mistakes. Include
  code-mixed / romanised forms where people really write that way in this language (e.g. Hinglish for Hindi, Tanglish
  for Tamil), about 25% of templates. Every template must contain at least one placeholder; each placeholder at most once.
- names: 60 common first names (women and men, different communities of the region), in the language's script AND
  romanised (mix), some with surnames.
- places: 80 place strings people of this region would type: real district, town and village names of the region and of
  other states, in native script and romanised, some as "village, district" or "district, state" combinations.
- amounts: 40 amount patterns with {n} where a number goes ("{n} rupees", "₹{n}", "{n} हज़ार", "{n} लाख रुपये") plus 15
  fully written amounts without {n} ("दो लाख", "पचास हज़ार रुपये", "one and a half lakh").
- activities: for EACH of these catalog ids give 6-10 natural phrases in this language (native + romanised):
  dairy_farming, goat_rearing, poultry_backyard, poultry_layer, fisheries_pond, beekeeping, mustard_oil_mill,
  flour_mill, food_processing_home, grocery_kirana, agri_input_depot, tailoring, handloom_weaving, carpet_weaving,
  mobile_repair, beauty_parlour, tea_snack_stall.
- reasons: 60 short reason clauses (without the "because" word itself; templates supply cue words like because/kyunki/
  ஏனென்றால்).
- intents: for each intent EXCEPT provide_info, 40 varied natural messages in this language (native + some romanised).
- test: 60 realistic messages written freshly by you — NOT built from your templates, different wording — each fully
  marked up with every span that occurs, e.g. "namaste mera naam [NAME Rekha] hai [LOC Jaunpur] se hoon aur [AMT 20 hazar]
  bache hain, [ACT silai ka kaam] karna hai". Include hard cases: names that are also words, places that contain a
  language word ("[LOC Tamil Nadu]"), amounts in words, no punctuation, very short answers ("[AMT 5000]").
- testIntents: 60 fresh messages (not copies of "intents") with their intent, covering all ten intents (provide_info too).

Validate with node before finishing: valid JSON; templates each contain ≥1 known placeholder and no unknown ones; every
test markup bracket is well-formed ("[LABEL text]" with LABEL in NAME LOC AMT ACT REASON); all 17 activity ids present;
all 9 intents (excluding provide_info) present in "intents"; counts at least as specified. Report in under 60 words.

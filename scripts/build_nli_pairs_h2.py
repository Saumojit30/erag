"""Build the H2 NLI evaluation pair set (60 pairs, 20/20/20) from dev.jsonl.

Selection rule (deterministic): dev questions in file order with >=2 gold
paragraphs and a 4-digit year in the gold paragraphs; first 20 taken.
Each question contributes 1 supported + 1 contradicted + 1 unresolved pair.
Hypotheses were hand-written from the gold paragraphs; the full
spec (qid + the three hypotheses per question) is hardcoded in SPEC below.
no model output or stored trace claim was used.

Validation performed by this script before writing:
- exactly 60 pairs, 20 per class
- no hypothesis is a (normalized) substring of any premise sentence or of the
  joined premise text
- contradicted hypothesis contains the flipped value; the original value is in
  the premise; contradicted differs from its supported sibling only in the
  flipped fact (checked by string replacement)
- unresolved key entity does not appear in the premise text
"""
import json, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data/manifests/dev.jsonl"
OUT = ROOT / "data/nli_eval_pairs.jsonl"

rows = {}
for l in open(DEV):
    r = json.loads(l)
    rows[r["_id"]] = r

def gold_paras(r):
    titles = {t for t, _ in r["supporting_facts"]}
    return [(t, s) for t, s in r["context"] if t in titles]

def norm(s):
    s = unicodedata.normalize("NFKD", s).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# (qid, supported, contradicted, flipped_fact, unresolved, unresolved_absent_entity)
SPEC = [
 ("5a82930655429966c78a6a5e",
  "The University of Central Florida, a public research university in Orlando, was represented by its football team in the 2010 college season.",
  "The University of Central Florida, a public research university in Orlando, was represented by its football team in the 2011 college season.",
  "2010 -> 2011 (season year of the UCF Knights football team)",
  "The University of Miami's football team won the national championship in 2001.",
  "University of Miami"),
 ("5ae07b0155429945ae95935d",
  "Thomas Mann, a German novelist, received the Nobel Prize in Literature in 1929.",
  "Thomas Mann, a German novelist, received the Nobel Prize in Literature in 1939.",
  "1929 -> 1939 (year Thomas Mann won the Nobel Prize in Literature)",
  "The German novelist Heinrich Boll won the Nobel Prize in Literature in 1972.",
  "Heinrich Boll"),
 ("5a820897554299676cceb1f4",
  "Mike Mills, a founding member of R.E.M., played bass guitar on the band's debut album Murmur, which came out in 1983.",
  "Mike Mills, a founding member of R.E.M., played bass guitar on the band's debut album Murmur, which came out in 1985.",
  "1983 -> 1985 (release year of the album Murmur)",
  "The bass guitarist John Paul Jones was a founding member of the rock band Led Zeppelin.",
  "John Paul Jones"),
 ("5adc94dc5542990d50227cad",
  "The comic character Archie Andrews was created in 1941 and first appeared in Pep Comics.",
  "The comic character Archie Andrews was created in 1951 and first appeared in Pep Comics.",
  "1941 -> 1951 (year Archie Andrews was created)",
  "The comic character Batman was created in 1939 and first appeared in Detective Comics.",
  "Batman"),
 ("5ae113de55429901ffe4ad51",
  "Vatican City, the country where the scholar Berthold Louis Ullman died, covers about 110 acres.",
  "Vatican City, the country where the scholar Berthold Louis Ullman died, covers about 210 acres.",
  "110 acres -> 210 acres (area of Vatican City)",
  "The country of Monaco covers about 200 hectares and is located on the French Riviera.",
  "Monaco"),
 ("5abfdfcb5542997d642958fe",
  "Mark Dacascos, an American actor and martial artist, starred in the 1994 film Double Dragon and played Mani in Brotherhood of the Wolf.",
  "Mark Dacascos, an American actor and martial artist, starred in the 1996 film Double Dragon and played Mani in Brotherhood of the Wolf.",
  "1994 -> 1996 (release year of the film Double Dragon)",
  "The martial artist Bruce Lee starred in the 1973 film Enter the Dragon.",
  "Bruce Lee"),
 ("5adfcb5455429906c02daa48",
  "Ardal O'Hanlon played Father Dougal McGuire in Father Ted and a detective in Death in Paradise.",
  "Kris Marshall played Father Dougal McGuire in Father Ted and a detective in Death in Paradise.",
  "Ardal O'Hanlon -> Kris Marshall (actor who played Father Dougal McGuire)",
  "The actor Rowan Atkinson played the vicar in the television series The Vicar of Dibley.",
  "Rowan Atkinson"),
 ("5a865bbf5542991e77181615",
  "Slimer, a character from the Ghostbusters franchise, appears in the 2016 film starring Melissa McCarthy.",
  "Slimer, a character from the Ghostbusters franchise, appears in the 2018 film starring Melissa McCarthy.",
  "2016 -> 2018 (release year of the Ghostbusters film starring Melissa McCarthy)",
  "The character Gizmo appears in the 1984 film Gremlins.",
  "Gizmo"),
 ("5ac3dfb15542995c82c4ac71",
  "Karel Bossart, born in 1904, was a pioneering rocket designer who created the Atlas ICBM.",
  "Karel Bossart, born in 1914, was a pioneering rocket designer who created the Atlas ICBM.",
  "1904 -> 1914 (Karel Bossart's birth year)",
  "The engineer Robert Goddard designed the first liquid-fueled rocket in 1926.",
  "Robert Goddard"),
 ("5adda8d45542995b365fab59",
  "Carol Ann Duffy, a Scottish poet and playwright, wrote the poem Havisham in 1993.",
  "Carol Ann Duffy, a Scottish poet and playwright, wrote the poem Havisham in 1998.",
  "1993 -> 1998 (year the poem Havisham was written)",
  "The Scottish poet Robert Burns wrote the poem Tam o' Shanter in 1790.",
  "Robert Burns"),
 ("5abb01025542992ccd8e7eab",
  "The Abscam sting operation was run by the FBI in the late 1970s and early 1980s.",
  "The Abscam sting operation was run by the FBI in the late 1960s and early 1970s.",
  "late 1970s and early 1980s -> late 1960s and early 1970s (period of the Abscam sting operation)",
  "The FBI sting operation known as Operation Greylord took place in Chicago in the 1980s.",
  "Operation Greylord"),
 ("5a7380e855429905862fe041",
  "The astrophysicist Joan Feynman, born in 1927, advanced research on solar wind particles and on how the Sun and Earth interact.",
  "The astrophysicist Joan Feynman, born in 1937, advanced research on solar wind particles and on how the Sun and Earth interact.",
  "1927 -> 1937 (Joan Feynman's birth year)",
  "The astrophysicist Vera Rubin discovered evidence for dark matter in the 1970s.",
  "Vera Rubin"),
 ("5a7335b55542992359bc3290",
  "Taylor Swift's album Red was released in 2012 by Big Machine Records.",
  "Taylor Swift's album Red was released in 2014 by Big Machine Records.",
  "2012 -> 2014 (release year of Taylor Swift's album Red)",
  "Adele's album 25 was released in 2015 by XL Recordings.",
  "Adele"),
 ("5adffb4655429925eb1afbbf",
  "In 2015, the T'Pau song China in Your Hand was voted the nation's 11th favourite 1980s number one.",
  "In 2016, the T'Pau song China in Your Hand was voted the nation's 11th favourite 1980s number one.",
  "2015 -> 2016 (year of the ITV poll vote for China in Your Hand)",
  "In 2015, the song Take On Me was voted the nation's favourite 1980s number one.",
  "Take On Me"),
 ("5a734acf5542991f9a20c6ec",
  "Shirley Manson, born in 1966, is younger than Jim Kerr, who was born in 1959.",
  "Shirley Manson, born in 1966, is younger than Jim Kerr, who was born in 1969.",
  "1959 -> 1969 (Jim Kerr's birth year)",
  "The singer Dolores O'Riordan, born in 1971, was younger than the singer Shirley Manson.",
  "Dolores O'Riordan"),
 ("5a8c7703554299585d9e36b9",
  "Douglas Murray, a British commentator, is an associate director of the Henry Jackson Society.",
  "Douglas Murray, a British commentator, is an associate director of the Centre for Social Cohesion.",
  "Henry Jackson Society -> Centre for Social Cohesion (organisation where Murray is associate director)",
  "The commentator Owen Jones is an associate director of the Fabian Society.",
  "Owen Jones"),
 ("5a8f979255429918e830d288",
  "Before moving to Shea Stadium, the New York Jets played at the Polo Grounds, which is just north of Central Park.",
  "Before moving to Shea Stadium, the New York Jets played at the Polo Grounds, which is just south of Central Park.",
  "just north of Central Park -> just south of Central Park (location of the Polo Grounds relative to Central Park)",
  "The New York Giants played at Yankee Stadium before moving to the Meadowlands.",
  "Yankee Stadium"),
 ("5a8ec02e5542995a26add501",
  "Check It Out! with Dr. Steve Brule, starring John C. Reilly, was produced by Abso Lutely Productions.",
  "Check It Out! with Dr. Steve Brule, starring Eric Wareheim, was produced by Abso Lutely Productions.",
  "John C. Reilly -> Eric Wareheim (star of Check It Out! with Dr. Steve Brule)",
  "The sketch comedy series Portlandia, starring Fred Armisen, was produced by Broadway Video.",
  "Portlandia"),
 ("5adde99b5542992200553ba1",
  "The 1952 film Thunderbirds featured the exploits of the 45th Infantry Division, part of the Oklahoma Army National Guard.",
  "The 1962 film Thunderbirds featured the exploits of the 45th Infantry Division, part of the Oklahoma Army National Guard.",
  "1952 -> 1962 (release year of the film Thunderbirds)",
  "The 1952 film High Noon starred Gary Cooper as a marshal in the New Mexico Territory.",
  "High Noon"),
 ("5ab2da13554299194fa93542",
  "Elliot Fletcher, born in 1996, is the son of Julia Fletcher and John DeMita.",
  "Elliot Fletcher, born in 1993, is the son of Julia Fletcher and John DeMita.",
  "1996 -> 1993 (Elliot Fletcher's birth year)",
  "The actor Elliot Page, born in 1987, is known for his work on the television series The Umbrella Academy.",
  "Elliot Page"),
]

pairs = []
for i, (qid, sup, con, flip, unres, absent_ent) in enumerate(SPEC):
    r = rows[qid]
    gp = gold_paras(r)
    premise = [s.strip() for _, ss in gp for s in ss]
    premise_text = " ".join(premise)
    # --- validation ---
    for hyp in (sup, con, unres):
        nh = norm(hyp)
        for s in premise:
            assert nh not in norm(s), f"hypothesis is substring of a premise sentence: {hyp}"
        assert nh not in norm(premise_text), f"hypothesis is substring of joined premise: {hyp}"
    # contradicted differs from supported only in the flipped fact
    old, new = [p.strip() for p in flip.split("->")]
    # flip string is "OLD -> NEW (description)"; extract old/new before the parenthesis
    old = old
    new = new.split("(")[0].strip()
    assert old in sup, f"original value not in supported claim: {old!r} / {sup!r}"
    assert new in con, f"flipped value not in contradicted claim: {new!r} / {con!r}"
    assert sup.replace(old, new) == con, f"contradicted != supported with one replacement:\n{sup}\n{con}"
    assert old in premise_text, f"original value not in premise: {old!r}"
    # unresolved entity absent from premise
    assert norm(absent_ent) not in norm(premise_text), f"unresolved entity present in premise: {absent_ent}"
    for gold, hyp in (("supported", sup), ("contradicted", con), ("unresolved", unres)):
        pairs.append({
            "id": f"nli{len(pairs)+1:03d}",
            "qid": qid,
            "gold": gold,
            "premise": premise,
            "hypothesis": hyp,
            "flipped_fact": flip if gold == "contradicted" else None,
        })

assert len(pairs) == 60, len(pairs)
from collections import Counter
assert Counter(p["gold"] for p in pairs) == {"supported": 20, "contradicted": 20, "unresolved": 20}
assert len({p["qid"] for p in pairs}) == 20
with open(OUT, "w") as f:
    for p in pairs:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")
print(f"wrote {len(pairs)} pairs to {OUT} from {len(SPEC)} questions — all validations passed")

import os
import requests
import re
from icalendar import Calendar, Event

# Retrieve the ICS_URL from environment variables
ICS_URL = os.environ.get('ICS_URL')

# Optional: Check if the variable is set and raise an error if not
if not ICS_URL:
    raise ValueError("Missing ICS_URL environment variable. Please set it in your Render dashboard.")


def clean_event_summary(summary):
    """
    Rensar händelsens sammanfattning enligt följande:
      - Tar bort strängen 'Aktivitetstyp'.
      - Tar bort oönskade kurskoder (BMA401, BMK101, KUBM26) men behåller BMA451.
      - Om sammanfattningen innehåller 'Moment:' extraheras texten efter detta.
         - Om den extraherade texten börjar med "Laboration Klinisk hematologi:" tas en avslutande " : Okänd" bort.
         - För andra fall extraheras texten upp till första kolon.
    """
    if summary is None:
        return ""

    # Ta bort 'Aktivitetstyp'
    summary = re.sub(r'Aktivitetstyp', '', summary)

    # Ta bort oönskade kurskoder
    undesired_codes = ["BMA401", "BMK101", "KUBM26"]
    for code in undesired_codes:
        summary = re.sub(r'\b' + code + r'\b,?\s*', '', summary)

    # Rensa eventuella inledande kommatecken
    summary = re.sub(r'^\s*,\s*', '', summary)

    # Om texten innehåller "Moment:" så extrahera det relevanta innehållet
    if "Moment:" in summary:
        # Extrahera allt efter "Moment:"
        moment_text = summary.split("Moment:", 1)[1].strip()
        # Om det är ett "Laboration Klinisk hematologi:"-moment
        if moment_text.startswith("Laboration Klinisk hematologi:"):
            # Ta bort en eventuell avslutning " : Okänd"
            moment_text = re.sub(r'\s*:\s*Okänd$', '', moment_text)
            return moment_text.strip()
        else:
            # För andra moment: extrahera texten upp till första kolon
            moment_pattern = r'^([^:]+)'
            match = re.search(moment_pattern, moment_text)
            if match:
                return match.group(1).strip()
            else:
                return moment_text.strip()
    else:
        return summary.strip()


def should_include_by_group(summary: str) -> bool:
    """
    Returnerar True om eventet ska behållas:

      - Om ingen grupp nämns alls -> behåll eventet.
      - Om grupper nämns -> behåll endast om någon av grupperna är:
        * 'Grupp C'
        * 'Grupp 4'
      - Matchning är case-insensitive.
    """
    if summary is None:
        return True

    text = summary

    # Hitta segment efter 'Grupp' som kan innehålla bokstäver/siffror och +/komma/whitespace
    # Exempel matchar: 'Grupp C', 'Grupp 4', 'Grupp 2 + 4', 'Grupp A + C'
    group_parts = re.findall(r'grupp\s*([A-Za-z0-9\s\+\,&]+)', text, flags=re.IGNORECASE)

    # Om ingen "Grupp" hittas -> behåll eventet
    if not group_parts:
        return True

    allowed = {"4", "c"}

    for part in group_parts:
        # Dela upp på +, komma, & osv
        tokens = re.split(r'[\+\,&]', part)
        for token in tokens:
            t = token.strip().lower()
            if not t:
                continue
            # Hantera 'c', '4', ev. 'grupp c' som redan fångats efter 'grupp'
            if t in allowed:
                return True

    # Om vi kom hit fanns grupper, men ingen av dem var C eller 4
    return False


def clean_calendar():
    """
    Hämtar ICS-kalendern, rensar varje VEVENT med den modifierade sammanfattningen
    och returnerar den nya kalendern som iCal-data.

    Alla events utan grupper behålls.
    Events med grupper behålls endast om de innehåller Grupp C och/eller Grupp 4.
    """
    response = requests.get(ICS_URL)
    response.raise_for_status()

    original_cal = Calendar.from_ical(response.text)

    clean_cal = Calendar()
    clean_cal.add('prodid', '-//Cleaned HKR Calendar//EN')
    clean_cal.add('version', '2.0')

    for component in original_cal.walk():
        if component.name == "VEVENT":
            raw_summary = component.get('summary')

            # Filtrera på grupp-info UTIFRÅN ORIGINALTEXTEN
            if not should_include_by_group(raw_summary):
                continue

            cleaned_summary = clean_event_summary(raw_summary)

            clean_event = Event()
            clean_event.add('summary', cleaned_summary)
            clean_event.add('dtstart', component.get('dtstart'))
            clean_event.add('dtend', component.get('dtend'))
            clean_event.add('location', component.get('location', ''))
            clean_event.add('description', component.get('description', ''))

            clean_cal.add_component(clean_event)

    return clean_cal.to_ical()


if __name__ == "__main__":
    # För testning: skriv ut den rensade iCal-strängen
    cleaned_ical = clean_calendar()
    print(cleaned_ical.decode('utf-8'))

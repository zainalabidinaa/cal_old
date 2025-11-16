import os
import requests
import re
from icalendar import Calendar, Event

# Fetch the ICS URL from environment variables
ICS_URL = os.environ.get('ICS_URL')

if not ICS_URL:
    raise ValueError("Missing ICS_URL environment variable. Please set it.")

def clean_event_summary(summary):
    """
    Extract only the text within 'Moment:' and remove 'Aktivitetstyp' from the summary.
    """
    if summary is None:
        return ""

    # Remove 'Aktivitetstyp' explicitly (word itself)
    summary = re.sub(r'Aktivitetstyp', '', summary)

    # Extract Moment from the summary
    moment_pattern = r'Moment:([^:]+)'
    match = re.search(moment_pattern, summary)
    
    if match:
        return match.group(1).strip()  # Return only the extracted text, trimmed of whitespace
    else:
        return summary.strip()  # Return cleaned summary without 'Aktivitetstyp'


def should_keep_event(summary: str) -> bool:
    """
    Behåll event enligt följande regler:
      - Om det INTE finns någon 'grupp' nämnd -> behåll.
      - Om det finns grupp(er) nämnda:
           behåll ENDAST om någon av grupperna är 'Grupp 4' eller 'Grupp C'.
      - Exempeln:
           '... grupp 1'           -> tas bort
           '... grupp 2 + 4'       -> behålls
           '... grupp A, B, C'     -> behålls (pga C)
    """

    if summary is None:
        return True

    text = summary.lower()

    # Leta efter "grupp ..." delar
    group_parts = re.findall(r'grupp\s*([a-z0-9 ,\+]+)', text, flags=re.IGNORECASE)

    # Om ingen "grupp" hittas -> behåll eventet
    if not group_parts:
        return True

    allowed = {"4", "c"}

    for part in group_parts:
        # Dela upp på '+' och ',' och trimma
        tokens = re.split(r'[+,]', part)
        for t in tokens:
            token = t.strip().lower()
            if token in allowed:
                return True

    # Det fanns grupp(er), men ingen 4 eller C
    return False


def clean_calendar():
    """
    Fetch and clean the calendar by extracting only relevant information.
    Includes all events EXCEPT those with groups that do NOT contain Grupp 4 or Grupp C.
    """
    # Fetch the original calendar data from the ICS URL
    response = requests.get(ICS_URL)
    response.raise_for_status()
    original_cal = Calendar.from_ical(response.text)
    
    # Create a new calendar for cleaned events
    clean_cal = Calendar()
    clean_cal.add('prodid', '-//Cleaned HKR Calendar//EN')
    clean_cal.add('version', '2.0')
    
    for component in original_cal.walk():
        if component.name == "VEVENT":  # Process only events
            raw_summary = component.get('summary')
            cleaned_summary = clean_event_summary(raw_summary)

            # Filtrera på grupper: behåll bara events utan gruppinfo
            # eller med Grupp 4 / Grupp C
            if not should_keep_event(cleaned_summary):
                continue

            clean_event = Event()
            clean_event.add('summary', cleaned_summary)
            clean_event.add('dtstart', component.get('dtstart'))
            clean_event.add('dtend', component.get('dtend'))
            clean_event.add('location', component.get('location', ''))
            clean_event.add('description', component.get('description', ''))
            
            # Add cleaned event to the new calendar
            clean_cal.add_component(clean_event)
    
    return clean_cal.to_ical()

if __name__ == "__main__":
    # Clean calendar and print output (for debugging or local testing)
    cleaned_ical = clean_calendar()
    print(cleaned_ical.decode('utf-8'))

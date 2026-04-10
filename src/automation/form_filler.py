import logging

from thefuzz import fuzz

from src.cv.models import ResumeData

logger = logging.getLogger(__name__)

# Map common form field labels to ResumeData fields
FIELD_MAPPING = {
    "first name": "first_name",
    "last name": "last_name",
    "nombre": "first_name",
    "apellido": "last_name",
    "email": "email",
    "correo": "email",
    "phone": "phone",
    "telefono": "phone",
    "mobile": "phone",
    "city": "city",
    "ciudad": "city",
    "linkedin": "linkedin_url",
    "linkedin profile": "linkedin_url",
    "website": "linkedin_url",
}


def get_field_value(label: str, resume: ResumeData) -> str | None:
    """Match a form field label to the corresponding resume data."""
    label_lower = label.lower().strip()

    # Direct match
    for pattern, field in FIELD_MAPPING.items():
        if pattern in label_lower:
            return _resolve_field(field, resume)

    # Fuzzy match
    best_match = None
    best_score = 0
    for pattern, field in FIELD_MAPPING.items():
        score = fuzz.partial_ratio(label_lower, pattern)
        if score > best_score and score >= 80:
            best_score = score
            best_match = field

    if best_match:
        return _resolve_field(best_match, resume)

    return None


def _resolve_field(field: str, resume: ResumeData) -> str:
    """Resolve a field name to the actual resume data value."""
    if field == "first_name":
        parts = resume.name.split()
        return parts[0] if parts else ""
    elif field == "last_name":
        parts = resume.name.split()
        return " ".join(parts[1:]) if len(parts) > 1 else ""
    elif field == "email":
        return resume.email
    elif field == "phone":
        return resume.phone
    elif field == "linkedin_url":
        return resume.linkedin_url
    elif field == "city":
        if resume.experiences and resume.experiences[0].location:
            return resume.experiences[0].location
        return ""
    return ""


async def fill_form_fields(page, resume: ResumeData, ai_advisor=None):
    """Detect and fill form fields on the current page."""
    from src.automation.humanize import human_type, random_delay

    # Find all visible input fields
    inputs = await page.locator("input:visible, textarea:visible, select:visible").all()

    for input_el in inputs:
        try:
            # Get the label or placeholder
            label = await _get_field_label(page, input_el)
            if not label:
                continue

            # Skip already filled fields
            current_value = await input_el.input_value()
            if current_value:
                continue

            # Try to match the field
            value = get_field_value(label, resume)

            # Fall back to AI advisor for unknown fields
            if value is None and ai_advisor:
                try:
                    from src.ai.form_advisor import answer_form_question

                    value = answer_form_question(resume, label)
                    logger.info(f"AI answered '{label}': {value[:50]}...")
                except Exception as e:
                    logger.debug(f"AI advisor failed for '{label}': {e}")

            if value:
                tag = await input_el.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    await input_el.select_option(label=value)
                else:
                    await input_el.clear()
                    await input_el.type(value, delay=80)

                await random_delay(0.3, 0.8)
                logger.info(f"Filled '{label}' with value")

        except Exception as e:
            logger.debug(f"Error filling field: {e}")
            continue


async def _get_field_label(page, element) -> str:
    """Get the label text for a form element."""
    # Try aria-label
    aria_label = await element.get_attribute("aria-label")
    if aria_label:
        return aria_label

    # Try placeholder
    placeholder = await element.get_attribute("placeholder")
    if placeholder:
        return placeholder

    # Try associated <label> element
    el_id = await element.get_attribute("id")
    if el_id:
        label = page.locator(f'label[for="{el_id}"]')
        if await label.count() > 0:
            return await label.first.inner_text()

    # Try name attribute
    name = await element.get_attribute("name")
    if name:
        return name.replace("_", " ").replace("-", " ")

    return ""

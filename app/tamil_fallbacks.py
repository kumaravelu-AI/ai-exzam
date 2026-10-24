from __future__ import annotations

import re


def _normalize_english(text: str) -> str:
    cleaned = (text or "").lower().replace("�", "'")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


# Deterministic translations used when no language model is available.  These
# cover the bundled Year 6 lessons, so mock mode still preserves the English
# meaning instead of displaying a generic Tamil placeholder.
_KNOWN_TRANSLATIONS = {
    # Microorganisms
    "microorganisms are tiny living things that are usually too small to see clearly with only our eyes":
        "நுண்ணுயிரிகள் என்பவை மிகச் சிறிய உயிரினங்கள். அவற்றை வெறும் கண்களால் தெளிவாகப் பார்க்க முடியாது.",
    "microorganisms are very small living things that cannot be seen with naked eyes":
        "நுண்ணுயிரிகள் என்பவை மிகச் சிறிய உயிரினங்கள். அவற்றை வெறும் கண்களால் பார்க்க முடியாது.",
    "what are microorganisms": "நுண்ணுயிரிகள் என்றால் என்ன?",
    "why do we need a microscope to see microorganisms":
        "நுண்ணுயிரிகளைப் பார்க்க நுண்ணோக்கி ஏன் தேவை?",
    "give two examples of microorganisms": "நுண்ணுயிரிகளுக்கு இரண்டு எடுத்துக்காட்டுகள் சொல்லுங்கள்.",
    "is bacteria a microorganism": "பாக்டீரியா ஒரு நுண்ணுயிரியா?",
    "is a bird a microorganism why": "பறவை ஒரு நுண்ணுயிரியா? ஏன்?",
    "true or false all microorganisms are harmful": "சரி அல்லது தவறு: எல்லா நுண்ணுயிரிகளும் தீங்கு விளைவிப்பவையா?",
    "which one is a microorganism bacteria tiger rock or mango tree":
        "இவற்றில் நுண்ணுயிரி எது: பாக்டீரியா, புலி, கல் அல்லது மாமரம்?",
    "why is air not a microorganism": "காற்று ஏன் நுண்ணுயிரி அல்ல?",
    "which microorganism helps bread rise": "ரொட்டி உயர எந்த நுண்ணுயிரி உதவுகிறது?",
    "give one example of a useful microorganism": "பயனுள்ள நுண்ணுயிரிக்கு ஓர் எடுத்துக்காட்டு சொல்லுங்கள்.",
    "are all microorganisms harmful explain": "எல்லா நுண்ணுயிரிகளும் தீங்கு விளைவிப்பவையா? விளக்குங்கள்.",
    "give one example of a useful microorganism in daily life":
        "அன்றாட வாழ்வில் பயனுள்ள நுண்ணுயிரிக்கு ஓர் எடுத்துக்காட்டு சொல்லுங்கள்.",
    "how can harmful microorganisms affect us": "தீங்கு விளைவிக்கும் நுண்ணுயிரிகள் நம்மை எவ்வாறு பாதிக்கலாம்?",
    "they are too tiny to be seen clearly": "அவை மிகச் சிறியவை; அதனால் அவற்றைத் தெளிவாகப் பார்க்க முடியாது.",
    "bacteria is a microorganism": "பாக்டீரியா ஒரு நுண்ணுயிரி.",
    "not all microorganisms are harmful some are useful":
        "எல்லா நுண்ணுயிரிகளும் தீங்கு விளைவிப்பவை அல்ல. சில நுண்ணுயிரிகள் பயனுள்ளவை.",
    "some microorganisms are useful": "சில நுண்ணுயிரிகள் பயனுள்ளவை.",
    "useful microorganisms help in food making such as yogurt and bread":
        "தயிர் மற்றும் ரொட்டி போன்ற உணவுகளைத் தயாரிக்க பயனுள்ள நுண்ணுயிரிகள் உதவுகின்றன.",
    "harmful microorganisms can spoil food or make us sick":
        "தீங்கு விளைவிக்கும் நுண்ணுயிரிகள் உணவைக் கெடுக்கலாம் அல்லது நோயை ஏற்படுத்தலாம்.",

    # Relationships among living things
    "living things interact with one another to get what they need":
        "உயிரினங்கள் தங்களுக்குத் தேவையானவற்றைப் பெற ஒன்றுடன் ஒன்று தொடர்பு கொள்கின்றன.",
    "why do living things interact with each other": "உயிரினங்கள் ஏன் ஒன்றுடன் ஒன்று தொடர்பு கொள்கின்றன?",
    "what is competition among living things": "உயிரினங்களுக்கு இடையிலான போட்டி என்றால் என்ன?",
    "give one example of animals competing for food": "உணவுக்காகப் போட்டியிடும் விலங்குகளுக்கு ஓர் எடுத்துக்காட்டு சொல்லுங்கள்.",
    "what is a predator": "வேட்டையாடி என்றால் என்ன?",
    "what is prey": "இரை என்றால் என்ன?",
    "true or false living things never depend on each other": "சரி அல்லது தவறு: உயிரினங்கள் ஒன்றையொன்று சார்ந்திருப்பதில்லை.",
    "why do plants compete for sunlight": "தாவரங்கள் சூரிய ஒளிக்காக ஏன் போட்டியிடுகின்றன?",

    # Food preservation
    "food preservation helps food last longer by slowing or stopping spoilage":
        "உணவு கெடுவதை மெதுவாக்குவதன் அல்லது தடுப்பதன் மூலம், உணவு நீண்ட நாட்கள் கெடாமல் இருக்க உணவு பாதுகாப்பு உதவுகிறது.",
    "what is food preservation": "உணவு பாதுகாப்பு என்றால் என்ன?",
    "why do we preserve food": "நாம் உணவை ஏன் பாதுகாக்கிறோம்?",
    "how can microorganisms spoil food": "நுண்ணுயிரிகள் உணவை எவ்வாறு கெடுக்கின்றன?",
    "give two methods of food preservation": "உணவைப் பாதுகாக்கும் இரண்டு முறைகளைச் சொல்லுங்கள்.",
    "which method keeps food very cold freezing drying or salting":
        "உணவை மிகவும் குளிராக வைத்திருக்கும் முறை எது: உறையவைத்தல், உலர்த்துதல் அல்லது உப்பிடுதல்?",
    "true or false food preservation can slow down microorganism growth":
        "சரி அல்லது தவறு: உணவு பாதுகாப்பு நுண்ணுயிரிகளின் வளர்ச்சியை மெதுவாக்கும்.",
    "why does drying help preserve food": "உலர்த்துதல் உணவைப் பாதுகாக்க ஏன் உதவுகிறது?",
    "give one daily life example of preserved food": "பாதுகாக்கப்பட்ட உணவுக்கு அன்றாட வாழ்விலிருந்து ஓர் எடுத்துக்காட்டு சொல்லுங்கள்.",

    # Living things and environment
    "a food chain shows how food passes from one living thing to another":
        "உணவு ஓர் உயிரினத்திலிருந்து மற்றோர் உயிரினத்திற்குச் செல்வதை உணவுச் சங்கிலி காட்டுகிறது.",
    "the arrow shows the direction in which food or energy moves":
        "உணவு அல்லது ஆற்றல் செல்லும் திசையை அம்புக்குறி காட்டுகிறது.",
    "plants are producers because they make their own food":
        "தாவரங்கள் தங்கள் உணவைத் தாங்களே தயாரிப்பதால் அவை உற்பத்தியாளர்கள்.",
    "animals are consumers because they eat other living things":
        "விலங்குகள் மற்ற உயிரினங்களை உண்பதால் அவை நுகர்வோர்கள்.",
    "what is a food chain": "உணவுச் சங்கிலி என்றால் என்ன?",
    "what does the arrow in a food chain show": "உணவுச் சங்கிலியில் உள்ள அம்புக்குறி எதைக் காட்டுகிறது?",
    "who is the producer in a food chain": "உணவுச் சங்கிலியில் உற்பத்தியாளர் எது?",
    "who is a consumer in a food chain": "உணவுச் சங்கிலியில் நுகர்வோர் எது?",
    "what is a herbivore": "தாவர உண்ணி என்றால் என்ன?",
    "what is a carnivore": "ஊன் உண்ணி என்றால் என்ன?",
    "what is an omnivore": "அனைத்துண்ணி என்றால் என்ன?",
}


def known_tamil_translation(english_text: str) -> str:
    """Return a reviewed Tamil equivalent for bundled lesson text, if known."""
    return _KNOWN_TRANSLATIONS.get(_normalize_english(english_text), "")

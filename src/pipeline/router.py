def route_intent(intent: str) -> str:
    """
    Routes the extracted intent to either the scoring engine
    or the generic chat responder.
    """
    intent = intent.lower().strip()
    
    scoring_intents = {
        "health_issue",
        "emergency",
        "symptom_report",
        "medical_query"
    }
    
    if intent in scoring_intents:
        return "scoring"
        
    return "chat"

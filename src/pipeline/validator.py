def validate_assessment(data: dict) -> bool:
    """
    Validates that the LLM output contains the required fields
    before it reaches the FastAPI backend.
    """
    required_keys = {"intent", "severity", "confidence"}
    
    # Check for missing keys
    if not required_keys.issubset(data.keys()):
        return False
        
    # Check types
    if not isinstance(data.get("intent"), str):
        return False
        
    if not isinstance(data.get("severity"), str):
        return False
        
    if not isinstance(data.get("confidence"), (int, float)):
        return False
        
    if not (0.0 <= data["confidence"] <= 1.0):
        return False
        
    # Symptoms is optional, but if present must be a list
    if "symptoms" in data and not isinstance(data["symptoms"], list):
        return False
        
    return True

export const mockAssessments = [
  {
    id: 1,
    timestamp: new Date().toISOString(),
    patient_name: "Mr. Sharma",
    intent: "health_issue",
    symptoms: ["chest_pain", "breathing_problem"],
    severity: "critical",
    confidence: 0.95,
    score: 124,
    risk_level: "CRITICAL",
    category: "CARDIAC",
    action: "notify_caregiver_and_emergency_services",
    message: "Critical: chest_pain, breathing_problem detected. Calling caregiver and emergency services.",
    steps: [
      "Call emergency services (112) immediately.",
      "Notify registered caregiver via SMS.",
      "Keep the user calm and on the line."
    ]
  },
  {
    id: 2,
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    patient_name: "Mr. Sharma",
    intent: "health_issue",
    symptoms: ["fall_detected"],
    severity: "high",
    confidence: 0.90,
    score: 75,
    risk_level: "HIGH",
    category: "FALL",
    action: "notify_caregiver",
    message: "High risk: fall_detected. Notifying caregiver.",
    steps: [
      "Notify caregiver.",
      "Ask user if they can get up safely."
    ]
  },
  {
    id: 3,
    timestamp: new Date(Date.now() - 7200000).toISOString(),
    patient_name: "Mr. Sharma",
    intent: "health_issue",
    symptoms: ["dizziness"],
    severity: "medium",
    confidence: 0.85,
    score: 40,
    risk_level: "MEDIUM",
    category: "NEUROLOGICAL",
    action: "follow_up_questions",
    message: "Medium risk: dizziness. Asking follow-up questions.",
    steps: [
      "Ask how long it has been.",
      "Ask for severity on scale of 1-10."
    ]
  },
  {
    id: 4,
    timestamp: new Date(Date.now() - 86400000).toISOString(),
    patient_name: "Mr. Sharma",
    intent: "health_issue",
    symptoms: ["medicine_missed"],
    severity: "low",
    confidence: 1.0,
    score: 15,
    risk_level: "LOW",
    category: "MEDICATION",
    action: "monitor",
    message: "Low risk: medicine_missed. Monitor condition.",
    steps: [
      "Log interaction.",
      "Check back in 4 hours."
    ]
  },
  {
    id: 5,
    timestamp: new Date(Date.now() - 172800000).toISOString(),
    patient_name: "Mr. Sharma",
    intent: "health_issue",
    symptoms: ["dizziness"],
    severity: "low",
    confidence: 0.8,
    score: 25,
    risk_level: "LOW",
    category: "NEUROLOGICAL",
    action: "monitor",
    message: "Low risk: dizziness. Monitor condition.",
    steps: [
      "Log interaction."
    ]
  }
];

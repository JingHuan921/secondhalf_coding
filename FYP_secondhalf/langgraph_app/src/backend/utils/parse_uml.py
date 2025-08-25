import re

def extract_plantuml(text: str) -> str:
    """
    Extracts PlantUML content from a paragraph, including only the part from @startuml to @enduml.
    
    Args:
        text (str): The input paragraph that may contain PlantUML code
        
    Returns:
        str: The PlantUML code including @startuml and @enduml tags
        
    Raises:
        ValueError: If no PlantUML block is found in the text
    """
    # Use regex to find @startuml to @enduml block (case insensitive, multiline)
    pattern = r'@startuml.*?@enduml'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    
    if not match:
        raise ValueError("No PlantUML block found. Expected text to contain @startuml ... @enduml")
    
    return match.group(0)

input_text = """
Certainly! I will parse your System Requirements List (SRL), extract actors, use cases, and system boundary, and provide PlantUML code for a use case diagram. Functional requirements are mapped to use cases, and non-functional ones (e.g., “basic moderation”) are included as UML notes.

---

**Actors**
- User
- Food Delivery Service (Uber Eats, Grubhub, DoorDash)
- Recommendation Engine (internal, but shown as a subsystem for clarity)
- Community Moderator (optional, if moderation is not automated – otherwise, just a stereotype/note)

---

```plantuml
@startuml
' Actors
actor User
actor "Food Delivery Service" as FoodDeliveryService
actor "Community Moderator" as Moderator

' System Boundary
rectangle "Diet & Food App" {
  ' Use Cases: Food Diary Feature
  (Log Meal Manually) as U_LogMeal
  (Edit/Delete Meal Entry) as U_EditMeal
  (View Meal Summaries) as U_ViewSummary
  (Import Meals from Orders) as U_AutoImport
  (Get Nutrition Insights) as U_Insights

  ' Use Cases: Recommendations
  (Personalized Meal/Restaurant Recommendations) as U_Recommend
  (Update Preferences & Goals) as U_UpdatePrefs

  ' Use Cases: Community Platform
  (Create Post/Review/Photo) as U_PostReview
  (Comment or Like Posts) as U_Interact
  (Participate in Discussions/Forums) as U_Forum
  (Report Inappropriate Content) as U_ReportContent
  (Moderate Content) as U_Moderate

  ' Use Cases: Delivery Integration
  (Browse & Order Food) as U_BrowseOrder
  (View Past Delivery Orders) as U_ViewOrders
  
  ' Internal Subsystem for extensibility / clarity
  rectangle "Recommendation Engine" {
    (Generate Recommendations) as S_GenRecommend
    (Process User History) as S_ProcessHistory
    (Adapt to Updated Preferences) as S_UpdateReco
    (Explain Recommendations) as S_Explain
  }
}

' Associations: User to relevant use cases
User --> U_LogMeal
User --> U_EditMeal
User --> U_ViewSummary
User --> U_AutoImport
User --> U_Insights
User --> U_Recommend
User --> U_UpdatePrefs
User --> U_PostReview
User --> U_Interact
User --> U_Forum
User --> U_ReportContent
User --> U_BrowseOrder
User --> U_ViewOrders

' Moderator can moderate reported content (if human moderation exists)
Moderator --> U_Moderate

' Food Delivery Service to import and integrate meal/order data
FoodDeliveryService --> U_AutoImport
FoodDeliveryService --> U_BrowseOrder

' Recommendation engine internal logic for recommendations
U_Recommend .down.> S_GenRecommend : <<include>>
U_UpdatePrefs .down.> S_UpdateReco : <<include>>
U_Recommend .down.> S_Explain : <<include>>
S_GenRecommend .down.> S_ProcessHistory : <<include>>
S_GenRecommend .down.> S_UpdateReco : <<extend>>

' Meal orders are automatically imported/logged after ordering
U_BrowseOrder .down.> U_AutoImport : <<include>>
U_BrowseOrder .down.> U_ViewOrders : <<include>>

' Reporting content is part of moderation workflow
U_ReportContent .down.> U_Moderate : <<include>>

' Notes for Non-Functional Requirements
note right of U_Moderate
  Basic moderation and reporting 
  of inappropriate content required.
end note

note right of U_Insights
  Insights must be easy to understand,
  including calorie, macros breakdown,
  and healthy streaks.
end note

note right of U_BrowseOrder
  Seamless ordering: completed
  without leaving the app.
  Aggregated menus from multiple platforms.
end note

@enduml
```

---

**Instructions:**  
- Copy the code above into a PlantUML renderer to visualize the Use Case Diagram.
- Edit or extend relationships as your implementation details become clearer.
- Non-functional requirements appear as notes/stereotypes per UML convention.  
- Actors, use cases, and system boundary reflect your requirements.

"""

uml_portion = extract_plantuml(input_text)



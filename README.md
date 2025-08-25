FYP_secondhalf/langgraph_app/src/backend/agents/analyst.py contains: 
- AgentState
- Analyst flow

To test out the flow: 
cd FYP_secondhalf/langgraph_app 
langgraph dev

input example: 
• ID: R1
○ Name: Food Diary Feature
○ Description: Implement a food diary that allows users to log their meals, track
dietary habits, and receive personalized insights. The diary should support
integration with food delivery services to seamlessly import meal data.
○ Priority: High
• ID: R2
○ Name: Personalized Recommendations
○ Description: Utilize machine learning algorithms to provide users with
personalized meal and restaurant recommendations based on their dietary
preferences, historical data, and health goals.
○ Priority: High
• ID: R3
○ Name: Community Platform
○ Description: Develop a community space within the app where users can share
reviews and experiences, interact with other food enthusiasts, and engage in
discussions.
○ Priority: Medium
• ID: R4
○ Name: Integration with Food Delivery Services
○ Description: Integrate with major food delivery platforms like Uber Eats,
Grubhub, and DoorDash to allow users to order food directly from the app.
○ Priority: High

Notes: 
- langgraph_app/src/agent/graph.py line 33 is the entry point to import defined graph 
- output for use case diagram (png file) is in FYP_secondhalf/langgraph_app/src/backend/output folder


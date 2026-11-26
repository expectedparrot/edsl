This project holds the coffee survey used in the EDSL screencasts. Save the questionnaire as survey.ep so later recording sessions can use it.

When asked to simulate responses, save the three named personas in agents.ep and the model panel in models.ep. Use a currently available text model from each requested provider. Run one interview per persona and model using private hosted inference, save results in simulated-results.ep, and display a compact table of all nine pairs. Include the usual morning drink and show when the brew question was skipped.

When asked to send the survey to people, create a live respondent link with the source survey private. Save the successful ep humanize create JSON envelope in deployment.json and reuse that deployment when retrieving responses. This demo uses the respondent link for distribution. Save the completed human responses in human-results.ep and show the answers.

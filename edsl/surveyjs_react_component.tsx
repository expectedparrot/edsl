import React, { useEffect, useState } from "react";
import { Model } from "survey-core";
import { Survey } from "survey-react-ui";
import "survey-core/survey-core.min.css";

interface EDSLSurveyProps {
  surveyJson: any;
  onComplete?: (result: any) => void;
  onValueChanged?: (sender: any, options: any) => void;
  className?: string;
  theme?: string;
}

/**
 * React component that renders an EDSL survey using SurveyJS.
 * 
 * This component takes a converted EDSL survey JSON and renders it using
 * the SurveyJS React library. It provides callbacks for completion and
 * value changes.
 */
function EDSLSurveyComponent({
  surveyJson,
  onComplete,
  onValueChanged,
  className = "",
  theme = "default"
}: EDSLSurveyProps) {
  const [survey, setSurvey] = useState<Model | null>(null);

  useEffect(() => {
    if (surveyJson) {
      const surveyModel = new Model(surveyJson);
      
      // Set up completion handler
      if (onComplete) {
        surveyModel.onComplete.add((sender, options) => {
          onComplete({
            data: sender.data,
            surveyResult: sender,
            options
          });
        });
      }
      
      // Set up value change handler
      if (onValueChanged) {
        surveyModel.onValueChanged.add(onValueChanged);
      }
      
      // Apply theme if specified
      if (theme !== "default") {
        surveyModel.applyTheme(theme);
      }
      
      setSurvey(surveyModel);
    }
  }, [surveyJson, onComplete, onValueChanged, theme]);

  if (!survey) {
    return <div>Loading survey...</div>;
  }

  return (
    <div className={`edsl-survey-container ${className}`}>
      <Survey model={survey} />
    </div>
  );
}

/**
 * Hook for converting EDSL survey data to SurveyJS format on the client side.
 * 
 * This would typically be used when the conversion happens in the browser
 * rather than on the server side.
 */
export function useEDSLSurveyConverter() {
  const convertEDSLSurvey = (edslSurveyData: any, title?: string) => {
    // This would call the Python converter via an API endpoint
    // or use a JavaScript port of the converter
    return fetch('/api/convert-edsl-survey', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        survey: edslSurveyData,
        title: title
      })
    }).then(response => response.json());
  };

  return { convertEDSLSurvey };
}

/**
 * Complete example component showing how to use the EDSL Survey converter
 * with a full React application.
 */
export function EDSLSurveyApp() {
  const [surveyJson, setSurveyJson] = useState(null);
  const [results, setResults] = useState(null);
  const { convertEDSLSurvey } = useEDSLSurveyConverter();

  // Example EDSL survey data (this would typically come from your backend)
  const exampleEDSLSurvey = {
    questions: [
      {
        question_name: "name",
        question_text: "What is your name?",
        question_type: "free_text"
      },
      {
        question_name: "favorite_color",
        question_text: "What is your favorite color?",
        question_type: "multiple_choice",
        question_options: ["Red", "Blue", "Green", "Yellow"]
      },
      {
        question_name: "hobbies",
        question_text: "What are your hobbies? (Select all that apply)",
        question_type: "checkbox",
        question_options: ["Reading", "Sports", "Music", "Gaming", "Travel"]
      }
    ]
  };

  useEffect(() => {
    // Convert the EDSL survey on component mount
    convertEDSLSurvey(exampleEDSLSurvey, "Sample EDSL Survey")
      .then(converted => setSurveyJson(converted))
      .catch(error => console.error("Failed to convert survey:", error));
  }, []);

  const handleSurveyComplete = (result: any) => {
    console.log("Survey completed:", result);
    setResults(result.data);
  };

  const handleValueChanged = (sender: any, options: any) => {
    console.log("Value changed:", options.name, options.value);
  };

  return (
    <div className="edsl-survey-app">
      <h1>EDSL Survey</h1>
      
      {surveyJson ? (
        <EDSLSurveyComponent
          surveyJson={surveyJson}
          onComplete={handleSurveyComplete}
          onValueChanged={handleValueChanged}
          className="my-survey"
        />
      ) : (
        <div>Loading survey...</div>
      )}
      
      {results && (
        <div className="survey-results">
          <h2>Survey Results</h2>
          <pre>{JSON.stringify(results, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default EDSLSurveyComponent;
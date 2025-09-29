"""Dynamic Interviewer for generating adaptive follow-up questions.

This module provides the DynamicInterviewer class, which can analyze an existing survey,
current answers, and an overall research objective to generate intelligent follow-up
questions. The class uses EDSL's question framework to create new QuestionFreeText
instances that will help researchers gather more targeted information.

The DynamicInterviewer is designed to work with ongoing survey sessions, allowing
researchers to adaptively probe deeper into interesting responses or explore
unexpected directions based on what respondents have already shared.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText


class DynamicInterviewer:
    """Generates adaptive follow-up questions based on survey context and research objectives.
    
    The DynamicInterviewer analyzes an existing survey, the answers provided so far,
    and an overall research objective to generate new QuestionFreeText instances that
    will help researchers gather more targeted and relevant information.
    
    This class is particularly useful for:
    - Adaptive interviews that evolve based on responses
    - Exploratory research where interesting responses warrant deeper investigation
    - Mixed-method approaches combining structured surveys with open-ended follow-ups
    - Research contexts where the most valuable questions emerge from initial responses
    
    Attributes:
        survey: The original survey that has been administered
        answer_dict: Dictionary of answers collected so far (question_name -> answer)
        overall_objective: The high-level research goal or question driving the investigation
    """
    
    def __init__(
        self,
        survey: "Survey",
        answer_dict: Dict[str, Any],
        overall_objective: str
    ):
        """Initialize a new DynamicInterviewer instance.
        
        Args:
            survey: The Survey object that has been administered to collect initial responses.
            answer_dict: Dictionary mapping question names to answers that have been collected.
                Should follow the format {"question_name": "answer_value", ...}
            overall_objective: String describing the high-level research objective or question
                that the researcher is trying to answer through this investigation.
                
        Examples:
            >>> from edsl import Survey
            >>> survey = Survey.example()
            >>> answers = {"q0": "yes", "q1": "I love learning new things"}
            >>> objective = "Understand what motivates students in their educational experience"
            >>> interviewer = DynamicInterviewer(survey, answers, objective)
            >>> interviewer.overall_objective
            'Understand what motivates students in their educational experience'
        """
        self.survey = survey
        self.answer_dict = answer_dict
        self.overall_objective = overall_objective
        
    def _analyze_survey_context(self) -> str:
        """Analyze the survey structure and current answers to create context summary.
        
        This method examines the survey questions, the answers provided so far,
        and identifies patterns, themes, or interesting responses that warrant
        further investigation.
        
        Returns:
            str: A formatted summary of the survey context and current state
        """
        # Get survey structure
        question_texts = [q.question_text for q in self.survey.questions]
        question_names = self.survey.question_names
        
        # Analyze all answers provided (now all questions are in the survey)
        answered_questions = []
        
        for q_name, answer in self.answer_dict.items():
            # Find the question in the current survey (including added follow-ups)
            matching_question = None
            for q in self.survey.questions:
                if q.question_name == q_name:
                    matching_question = q
                    break
            
            if matching_question:
                # Handle both simple answers and dict formats
                if isinstance(answer, dict):
                    if 'question' in answer and 'answer' in answer:
                        # Manual follow-up format
                        answered_questions.append(f"Q: {answer['question']}\nA: {answer['answer']}")
                    elif 'question_text' in answer and 'answer' in answer:
                        # Generated follow-up format
                        answered_questions.append(f"Q: {answer['question_text']}\nA: {answer['answer']}")
                    else:
                        answered_questions.append(f"Q: {matching_question.question_text}\nA: {str(answer)}")
                else:
                    answered_questions.append(f"Q: {matching_question.question_text}\nA: {answer}")
            else:
                # Question not found in survey (shouldn't happen but handle gracefully)
                if isinstance(answer, dict):
                    answered_questions.append(f"Q: [Unknown] {q_name}\nA: {str(answer)}")
                else:
                    answered_questions.append(f"Q: [Unknown] {q_name}\nA: {answer}")
        
        context_summary = f"""
SURVEY CONTEXT ANALYSIS:

Research Objective: {self.overall_objective}

Survey Structure:
- Total questions in survey: {len(self.survey.questions)}
- Questions answered so far: {len(self.answer_dict)}

Questions and Answers (in conversation order):
{chr(10).join(answered_questions) if answered_questions else "None yet"}

Remaining Survey Questions:
"""
        
        # Add unanswered questions
        unanswered = []
        for i, q in enumerate(self.survey.questions):
            if q.question_name not in self.answer_dict:
                unanswered.append(f"- {q.question_text}")
        
        if unanswered:
            context_summary += "\n".join(unanswered)
        else:
            context_summary += "All survey questions have been answered."
            
        return context_summary
        
    def _generate_follow_up_prompt(self) -> str:
        """Generate a prompt for creating an intelligent follow-up question.
        
        This method creates a detailed prompt that will be used with a language model
        to generate an appropriate follow-up question based on the survey context
        and research objective.
        
        Returns:
            str: A comprehensive prompt for follow-up question generation
        """
        context = self._analyze_survey_context()
        
        prompt = f"""You are an expert researcher helping to conduct an adaptive interview. Based on the survey context below, generate ONE highly targeted follow-up question that will help achieve the research objective.

{context}

INSTRUCTIONS FOR FOLLOW-UP QUESTION:
1. The question should directly advance the research objective: "{self.overall_objective}"
2. CRITICALLY EXAMINE each response for unfamiliar terms, concepts, or details that may need clarification
3. If the respondent mentions something that seems unusual, technical, or potentially made-up, ASK ABOUT IT DIRECTLY
4. PRIORITIZE asking about specific details, terms, places, or concepts mentioned in recent answers - especially if they seem unclear or unfamiliar
5. Look for interesting, unexpected, incomplete, or intriguing elements in the responses that warrant follow-up
6. Do not assume you understand specialized terminology - ask for clarification when in doubt
7. Do not personalize the question to the respondent by using their name or pronouns
8. Avoid asking broad, general questions that are similar to what has already been asked
9. Focus on the most recent response first - drill down into specifics that need explanation
10. The question should feel natural and conversational, building directly on what was just shared

QUESTION GENERATION PRIORITY:
- HIGHEST priority: Ask about unfamiliar terms, concepts, or details that need clarification or may not be real/standard
- Second priority: Ask about specific places, tools, techniques, or processes mentioned
- Third priority: Explore the emotional or experiential aspects of what was shared
- Fourth priority: Connect responses to the research objective in new ways

CRITICAL: If you encounter terms or concepts you're not certain about, ask for clarification rather than assuming their meaning.

Generate a single, well-crafted follow-up question that would be most valuable for this research. Return ONLY the question text, nothing else."""

        return prompt
        
    def generate_follow_up_question(
        self, 
        question_name: Optional[str] = None,
    ) -> "QuestionFreeText":
        """Generate a dynamic follow-up question based on the survey context.
        
        This method uses the survey context, existing answers, and research objective
        to generate an intelligent follow-up question that will help advance the
        research goals.
        
        Args:
            question_name: Optional name for the generated question. If not provided,
                a default name will be generated.
            model: Optional language model to use for generating the question.
                If not provided, a default model will be used.
                
        Returns:
            QuestionFreeText: A new question designed to gather additional insights
                based on the current survey context and research objective.
                
        Examples:
            >>> from edsl import Survey
            >>> survey = Survey.example()
            >>> answers = {"q0": "yes", "q2": "I love the creative subjects like art and music"}
            >>> objective = "Understand what specific aspects of school students find most engaging"
            >>> interviewer = DynamicInterviewer(survey, answers, objective)
            >>> follow_up = interviewer.generate_follow_up_question()
            >>> follow_up.question_type
            'free_text'
        """
        from edsl.questions import QuestionFreeText
        from uuid import uuid4
        
        # Generate a question name if not provided
        if question_name is None:
            question_name = f"follow_up_{str(uuid4())[:8]}"
            
        # Get the prompt for generating the follow-up question
        generation_prompt = self._generate_follow_up_prompt()
        
        # Create a meta-question to generate the follow-up question text
        meta_question = QuestionFreeText(
            question_name="follow_up_generator",
            question_text=generation_prompt
        )
        
            
        result = meta_question.run(verbose=False)
        generated_question_text = result.select("answer.follow_up_generator").first()
                    # Create and return the follow-up question
        follow_up_question = QuestionFreeText(
            question_name=question_name,
            question_text=generated_question_text,
        )     
        return follow_up_question
                    
    def get_context_summary(self) -> str:
        """Get a human-readable summary of the current interview context.
        
        Returns:
            str: Formatted summary of survey progress and context
        """
        return self._analyze_survey_context()
    
    def conduct_survey(self) -> Dict[str, Any]:
        """Conduct an interactive command line survey with dynamic follow-up questions.
        
        This method runs an interactive terminal session where:
        1. Initial survey questions are asked one by one
        2. User provides answers via command line input
        3. Dynamic follow-up questions are generated based on answers and research objective
        4. Process continues until user chooses to stop
        
        Returns:
            Dict[str, Any]: Complete dictionary of all answers collected during the session
            
        Examples:
            >>> from edsl import Survey, QuestionFreeText
            >>> q = QuestionFreeText(question_name="hobby", question_text="What's your favorite hobby?")
            >>> survey = Survey(questions=[q])
            >>> interviewer = DynamicInterviewer(survey, {}, "Understand leisure preferences")
            >>> answers = interviewer.conduct_survey()  # Interactive CLI session
        """
        print(f"\n🎯 Research Objective: {self.overall_objective}")
        print("=" * 60)
        print("Welcome to the Dynamic Interview Session!")
        print("Type 'quit' at any time to end the interview.\n")
        
        # Start with a copy of existing answers
        current_answers = self.answer_dict.copy()
        
        # First, ask any unanswered questions from the original survey
        for question in self.survey.questions:
            if question.question_name not in current_answers:
                print(f"\n📝 {question.question_text}")
                answer = input("Your answer: ").strip()
                
                if answer.lower() == 'quit':
                    print("\n👋 Interview ended by user.")
                    return current_answers
                    
                current_answers[question.question_name] = answer
                print(f"✓ Recorded answer for '{question.question_name}'")
        
        # Now enter the dynamic follow-up loop
        follow_up_count = 0
        max_follow_ups = 10  # Reasonable limit to prevent infinite loops
        
        while follow_up_count < max_follow_ups:
            print("\n🔄 Generating follow-up question based on your responses...")
            
            # Update this instance's answer_dict with all current answers
            self.answer_dict = current_answers
            
            try:
                # Generate a follow-up question using the updated context
                follow_up_question = self.generate_follow_up_question(
                    question_name=f"follow_up_{follow_up_count + 1}"
                )
                
                print(f"\n📝 {follow_up_question.question_text}")
                answer = input("Your answer: ").strip()
                
                if answer.lower() == 'quit':
                    print("\n👋 Interview ended by user.")
                    break
                    
                # Add the follow-up question to the survey so it appears in context
                self.survey.add_question(follow_up_question)
                
                # Record the answer (now as simple string since question is in survey)
                current_answers[follow_up_question.question_name] = answer
                print(f"✓ Recorded answer for '{follow_up_question.question_name}'")
                
                follow_up_count += 1
                
                # Ask if user wants to continue
                print("\n🤔 Continue with more follow-up questions? (y/n/quit)")
                continue_response = input("Continue? ").strip().lower()
                
                if continue_response in ['n', 'no', 'quit']:
                    print("\n👋 Interview completed.")
                    break
                elif continue_response not in ['y', 'yes', '']:
                    print("Please enter 'y' for yes, 'n' for no, or 'quit' to end.")
                    continue
                    
            except Exception as e:
                print(f"\n❌ Error generating follow-up question: {e}")
                print("You can continue manually or type 'quit' to end.")
                manual_input = input("Enter a follow-up question manually (or 'quit'): ").strip()
                
                if manual_input.lower() == 'quit':
                    break
                    
                if manual_input:
                    answer = input(f"Answer to '{manual_input}': ").strip()
                    if answer.lower() != 'quit':
                        current_answers[f"manual_follow_up_{follow_up_count + 1}"] = {
                            "question": manual_input,
                            "answer": answer
                        }
                        follow_up_count += 1
        
        if follow_up_count >= max_follow_ups:
            print(f"\n⏰ Reached maximum number of follow-up questions ({max_follow_ups}).")
        
        print("\n📊 Interview Summary:")
        print(f"Total questions answered: {len(current_answers)}")
        print("=" * 60)
        
        return current_answers


if __name__ == "__main__":
    from edsl import Survey, QuestionFreeText
    
    # Create a sample survey
    questions = [
        QuestionFreeText(
            question_name="favorite_hobby", 
            question_text="What is your favorite hobby and why do you enjoy it?"
        ),
        QuestionFreeText(
            question_name="learning_style", 
            question_text="How do you prefer to learn new things?"
        )
    ]
    
    survey = Survey(questions=questions)
    
    # Initialize the dynamic interviewer
    interviewer = DynamicInterviewer(
        survey=survey, 
        answer_dict={}, 
        overall_objective="Understand how people engage with their interests and learning preferences"
    )
    
    # Run the interactive command line interview
    print("Starting Dynamic Interview CLI Demo...")
    final_answers = interviewer.conduct_survey()
    
    # Display final results
    print("\n" + "=" * 60)
    print("🎉 FINAL INTERVIEW RESULTS:")
    print("=" * 60)
    for question_name, answer in final_answers.items():
        if isinstance(answer, dict):
            if 'question' in answer and 'answer' in answer:
                # Manual follow-up format
                print(f"\n{question_name}:")
                print(f"  Q: {answer['question']}")
                print(f"  A: {answer['answer']}")
            elif 'question_text' in answer and 'answer' in answer:
                # Generated follow-up format
                print(f"\n{question_name}:")
                print(f"  Q: {answer['question_text']}")
                print(f"  A: {answer['answer']}")
            else:
                # Fallback
                print(f"\n{question_name}: {str(answer)}")
        else:
            print(f"\n{question_name}: {answer}")
    print("\n" + "=" * 60) 

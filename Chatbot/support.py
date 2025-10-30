"""
RentoMojo Customer Support Chatbot
Domain: Customer Support
Tone: Formal Support Agent
Purpose: FAQ Answering based on JSONL knowledge base
"""

import json
import os
from typing import Dict, List, Optional
from openai import OpenAI
from difflib import SequenceMatcher

class RentoMojoSupportBot:
    def __init__(self, faq_file: str = "rentomojo_faqs.jsonl", api_key: str = None):
        """
        Initialize RentoMojo Customer Support Bot
        
        Args:
            faq_file: Path to JSONL file containing FAQs
            api_key: OpenAI API key
        """
        self.faq_file = faq_file
        self.conversation_history = []
        self.all_faqs = []  # Store all FAQ pairs
        self.client = None  # Will be set up later
        
        # Load FAQ data FIRST
        self.load_all_faqs()
        
        # Configure OpenAI API AFTER loading FAQs
        self.setup_openai_api(api_key)
        
        # Behavioral System Prompt - CRITICAL FOR FACTUAL RESPONSES
        self.system_prompt = self.create_behavioral_prompt()
        
        # Default parameters for factual, precise responses
        self.default_params = {
            'temperature': 0.1,      # Very low for factual answers
            'max_tokens': 400,       # Adequate for detailed responses
            'top_p': 0.8,           # Focused sampling
            'top_k': 20             # Limited token selection
        }
    
    def create_behavioral_prompt(self) -> str:
        """
        Create comprehensive behavioral prompt for the model
        This ensures the model acts as a formal customer support agent
        """
        return """You are a formal customer support agent for RentoMojo, an online furniture and appliance rental company.

YOUR ROLE AND BEHAVIOR:
1. You MUST answer questions ONLY using the provided RentoMojo knowledge base
2. Maintain a professional, formal, and courteous tone at all times
3. Provide accurate, factual information without speculation or assumptions
4. If information is not in the knowledge base, clearly state you cannot answer
5. Never make up information or use external knowledge
6. Be concise but comprehensive - include all relevant details from the knowledge base
7. Use proper business language and complete sentences

RESPONSE GUIDELINES:
✓ Always greet professionally
✓ Provide step-by-step instructions when available in knowledge base
✓ Include relevant policy details (charges, timelines, requirements)
✓ End with appropriate closing or offer to help further
✓ Reference the chat feature for complex issues when mentioned in knowledge base

RESTRICTIONS:
✗ Do NOT answer questions outside the RentoMojo knowledge base
✗ Do NOT speculate or make assumptions
✗ Do NOT provide personal opinions
✗ Do NOT use casual or informal language
✗ Do NOT invent procedures, policies, or information

If a question cannot be answered from the knowledge base, respond:
"I apologize, but I do not have that specific information in my current knowledge base. For accurate assistance with this query, I recommend contacting our support team directly through the chat feature on our website or mobile app."

Remember: You are representing RentoMojo's customer support. Accuracy and professionalism are paramount."""

    def setup_openai_api(self, api_key: str = None):
        """Configure OpenAI API"""
        # Don't check environment variable automatically - always prompt if no key provided
        final_api_key = api_key
        
        if not final_api_key:
            # Check environment variable only if no key provided
            env_key = os.getenv('OPENAI_API_KEY')
            if not env_key:
                print("🔑 OpenAI API key not found.")
                final_api_key = input("Enter your OpenAI API key: ").strip()
                if not final_api_key:
                    raise ValueError("API key is required to run the bot.")
            else:
                final_api_key = env_key
        
        self.client = OpenAI(api_key=final_api_key)
        print("✅ OpenAI API configured successfully")

    def load_all_faqs(self):
        """
        Load ALL FAQ entries from JSONL file
        Extract question-answer pairs for context retrieval
        """
        try:
            if not os.path.exists(self.faq_file):
                print(f"❌ FAQ file '{self.faq_file}' not found.")
                return
            
            with open(self.faq_file, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        # Parse JSON line
                        entry = json.loads(line)
                        
                        # Extract Q&A from messages format
                        if 'messages' in entry:
                            messages = entry['messages']
                            question = None
                            answer = None
                            
                            for msg in messages:
                                if msg.get('role') == 'user':
                                    question = msg.get('content', '').strip()
                                elif msg.get('role') == 'assistant':
                                    answer = msg.get('content', '').strip()
                            
                            if question and answer:
                                self.all_faqs.append({
                                    'question': question,
                                    'answer': answer
                                })
                    
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Line {line_num}: Invalid JSON - {e}")
                        continue
            
            print(f"✅ Loaded {len(self.all_faqs)} FAQ entries from knowledge base")
            
            if len(self.all_faqs) == 0:
                print("⚠️  Warning: No FAQ entries loaded. Bot will have limited functionality.")
            
        except Exception as e:
            print(f"❌ Error loading FAQ file: {e}")
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def find_best_matching_faqs(self, user_question: str, top_k: int = 5) -> List[Dict]:
        """
        Find best matching FAQs based on question similarity
        Returns top_k most relevant FAQ entries
        """
        if not self.all_faqs:
            return []
        
        # Calculate similarity scores for all FAQs
        scored_faqs = []
        user_question_lower = user_question.lower()
        
        for faq in self.all_faqs:
            # Calculate similarity score
            similarity = self.calculate_similarity(user_question_lower, faq['question'].lower())
            
            # Also check for keyword matches
            question_words = set(user_question_lower.split())
            faq_words = set(faq['question'].lower().split())
            keyword_overlap = len(question_words & faq_words) / max(len(question_words), 1)
            
            # Combined score
            combined_score = (similarity * 0.7) + (keyword_overlap * 0.3)
            
            scored_faqs.append({
                'faq': faq,
                'score': combined_score
            })
        
        # Sort by score and return top_k
        scored_faqs.sort(key=lambda x: x['score'], reverse=True)
        return [item['faq'] for item in scored_faqs[:top_k]]
    
    def build_context_from_faqs(self, relevant_faqs: List[Dict]) -> str:
        """Build context string from relevant FAQs"""
        if not relevant_faqs:
            return "No relevant information found in knowledge base."
        
        context_parts = ["RENTOMOJO KNOWLEDGE BASE - RELEVANT FAQ ENTRIES:\n"]
        context_parts.append("=" * 80 + "\n")
        
        for idx, faq in enumerate(relevant_faqs, 1):
            context_parts.append(f"\n[FAQ Entry #{idx}]")
            context_parts.append(f"Question: {faq['question']}")
            context_parts.append(f"Answer: {faq['answer']}")
            context_parts.append("-" * 80)
        
        return "\n".join(context_parts)
    
    def generate_response(self, 
                         user_question: str,
                         temperature: float = None,
                         max_tokens: int = None,
                         top_p: float = None,
                         top_k: int = None) -> Dict:
        """
        Generate response using ChatGPT with provided parameters
        
        Args:
            user_question: User's question
            temperature: Randomness (0.0-1.0). Lower = more factual
            max_tokens: Maximum response length
            top_p: Nucleus sampling (0.0-1.0)
            top_k: Top-k sampling (Note: OpenAI doesn't support top_k, kept for compatibility)
        
        Returns:
            Dictionary with response and metadata
        """
        # Use default parameters if not provided
        temp = temperature if temperature is not None else self.default_params['temperature']
        tokens = max_tokens if max_tokens is not None else self.default_params['max_tokens']
        p = top_p if top_p is not None else self.default_params['top_p']
        k = top_k if top_k is not None else self.default_params['top_k']
        
        try:
            # Find relevant FAQs
            relevant_faqs = self.find_best_matching_faqs(user_question, top_k=5)
            
            # Build context
            context = self.build_context_from_faqs(relevant_faqs)
            
            # Construct prompt with behavioral instructions
            user_prompt = f"""{context}

CUSTOMER QUESTION:
{user_question}

INSTRUCTIONS FOR YOUR RESPONSE:
- Answer the customer's question using ONLY the information from the FAQ entries above
- Maintain a formal, professional tone
- Provide complete, accurate information
- Include step-by-step instructions if present in the knowledge base
- If the answer is not in the FAQs above, politely state you cannot answer
- Do not add information not present in the knowledge base

YOUR RESPONSE:"""
            
            # Generate response with specified parameters
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # You can change to "gpt-4" or "gpt-4-turbo" for better results
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temp,
                max_tokens=tokens,
                top_p=p,
                n=1
            )
            
            assistant_response = response.choices[0].message.content.strip()
            
            # Calculate confidence based on FAQ matching
            confidence = relevant_faqs[0] if relevant_faqs else None
            
            return {
                'response': assistant_response,
                'status': 'success',
                'parameters': {
                    'temperature': temp,
                    'max_tokens': tokens,
                    'top_p': p,
                    'top_k': k
                },
                'matched_faqs': len(relevant_faqs),
                'best_match_score': self.calculate_similarity(user_question, relevant_faqs[0]['question']) if relevant_faqs else 0.0
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error generating response: {e}")
            
            # Check if it's an API key error
            if "401" in error_msg or "invalid_api_key" in error_msg or "Incorrect API key" in error_msg:
                print("\n⚠️  Your API key appears to be invalid.")
                print("Please do one of the following:")
                print("1. Set environment variable: OPENAI_API_KEY=your-key")
                print("2. Get a new API key from: https://platform.openai.com/api-keys")
                print("3. Restart the bot and enter a valid key when prompted")
            
            return {
                'response': "I apologize, but I'm experiencing technical difficulties. Please try again or contact our support team.",
                'status': 'error',
                'error': str(e)
            }
    
    def interactive_session(self):
        """
        Start interactive customer support session
        Allows dynamic parameter adjustment
        """
        print("\n" + "=" * 80)
        print("🤵 RENTOMOJO CUSTOMER SUPPORT BOT")
        print("=" * 80)
        print(f"📚 Knowledge Base: {len(self.all_faqs)} FAQ entries loaded")
        print(f"🎯 Mode: Formal Support Agent | Purpose: FAQ Answering")
        print(f"🔧 Default Parameters: Temperature={self.default_params['temperature']}, "
              f"Max Tokens={self.default_params['max_tokens']}")
        print("\n💡 Commands:")
        print("   'params' - Adjust response parameters")
        print("   'reset'  - Reset to default parameters")
        print("   'stats'  - View current settings")
        print("   'quit'   - Exit")
        print("-" * 80)
        
        # Current parameters
        current_params = self.default_params.copy()
        
        while True:
            try:
                user_input = input("\n🧑 Customer: ").strip()
                
                if not user_input:
                    continue
                
                # Command handling
                if user_input.lower() == 'quit':
                    print("\n🤵 Thank you for contacting RentoMojo. Have a great day!")
                    break
                
                elif user_input.lower() == 'params':
                    current_params = self.adjust_parameters(current_params)
                    continue
                
                elif user_input.lower() == 'reset':
                    current_params = self.default_params.copy()
                    print("✅ Parameters reset to defaults")
                    self.show_current_params(current_params)
                    continue
                
                elif user_input.lower() == 'stats':
                    self.show_current_params(current_params)
                    continue
                
                # Generate response
                print("\n🔄 Processing your query...")
                response_data = self.generate_response(
                    user_question=user_input,
                    temperature=current_params['temperature'],
                    max_tokens=current_params['max_tokens'],
                    top_p=current_params['top_p'],
                    top_k=current_params['top_k']
                )
                
                # Display response
                print(f"\n🤖 RentoMojo Support:")
                print(f"{response_data['response']}")
                print(f"\n📊 Metadata:")
                print(f"   Status: {response_data['status']}")
                print(f"   Matched FAQs: {response_data.get('matched_faqs', 0)}")
                print(f"   Confidence: {response_data.get('best_match_score', 0):.2%}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Session ended by user.")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
    
    def adjust_parameters(self, current_params: Dict) -> Dict:
        """
        Allow user to adjust generation parameters
        Returns updated parameters
        """
        print("\n" + "=" * 80)
        print("🛠️  PARAMETER ADJUSTMENT")
        print("=" * 80)
        print("\nCurrent Parameters:")
        self.show_current_params(current_params)
        
        print("\n📝 Parameter Guide:")
        print("   Temperature (0.0-1.0): Lower = more factual, Higher = more creative")
        print("   Max Tokens (20-1000): Maximum length of response")
        print("   Top P (0.0-1.0): Nucleus sampling for diversity")
        print("   Top K (1-100): Number of top tokens considered (kept for compatibility)")
        print("\n💡 Recommended for factual answers: temp=0.1, tokens=400, top_p=0.8, top_k=20")
        print("-" * 80)
        
        try:
            temp_input = input(f"\nTemperature [Current: {current_params['temperature']}]: ").strip()
            if temp_input:
                temp = float(temp_input)
                current_params['temperature'] = max(0.0, min(1.0, temp))
            
            tokens_input = input(f"Max Tokens [Current: {current_params['max_tokens']}]: ").strip()
            if tokens_input:
                tokens = int(tokens_input)
                current_params['max_tokens'] = max(20, min(1000, tokens))
            
            top_p_input = input(f"Top P [Current: {current_params['top_p']}]: ").strip()
            if top_p_input:
                p = float(top_p_input)
                current_params['top_p'] = max(0.0, min(1.0, p))
            
            top_k_input = input(f"Top K [Current: {current_params['top_k']}]: ").strip()
            if top_k_input:
                k = int(top_k_input)
                current_params['top_k'] = max(1, min(100, k))
            
            print("\n✅ Parameters updated successfully!")
            self.show_current_params(current_params)
            
        except ValueError:
            print("❌ Invalid input. Parameters unchanged.")
        
        return current_params
    
    def show_current_params(self, params: Dict):
        """Display current parameter settings"""
        print(f"""
   Temperature:  {params['temperature']}
   Max Tokens:   {params['max_tokens']}
   Top P:        {params['top_p']}
   Top K:        {params['top_k']} (kept for compatibility)
        """)
    
    def test_bot(self):
        """Test the bot with sample questions"""
        print("\n" + "=" * 80)
        print("🧪 TESTING RENTOMOJO SUPPORT BOT")
        print("=" * 80)
        
        test_questions = [
            "What is RentoMojo?",
            "Which cities does RentoMojo operate in?",
            "How do I cancel my subscription?",
            "What documents do I need for KYC?",
            "What happens if I damage the product?"
        ]
        
        for idx, question in enumerate(test_questions, 1):
            print(f"\n[Test {idx}] Question: {question}")
            response = self.generate_response(question)
            print(f"Answer: {response['response'][:200]}...")
            print(f"Match Score: {response.get('best_match_score', 0):.2%}")
            print("-" * 80)


def main():
    """Main function to run the bot"""
    print("🚀 Starting RentoMojo Customer Support Bot...")
    print("📋 Loading knowledge base from JSONL file...")
    
    try:
        # Initialize bot
        bot = RentoMojoSupportBot("rentomojo_faqs.jsonl")
        
        if len(bot.all_faqs) == 0:
            print("⚠️  No FAQ data loaded. Please check your JSONL file.")
            return
        
        # Start interactive session
        bot.interactive_session()
        
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")


if __name__ == "__main__":
    main()
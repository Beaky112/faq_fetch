"""
Advanced Multi-Domain Tone-Adaptive Chatbot
Features:
- Trains on multiple JSONL files
- Adapts response tone to match user's tone
- Global and generic question handling
- Sentiment and tone analysis
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from difflib import SequenceMatcher
from collections import defaultdict


class ToneAdaptiveChatbot:
    def __init__(self, jsonl_files: List[str], api_key: str = None):
        """
        Initialize Tone-Adaptive Chatbot
        
        Args:
            jsonl_files: List of JSONL file paths
            api_key: OpenAI API key
        """
        self.jsonl_files = jsonl_files
        self.knowledge_base = []
        self.domain_map = defaultdict(list)
        self.client = None
        
        # Load all knowledge bases
        self.load_all_knowledge_bases()
        
        # Setup OpenAI API
        self.setup_openai_api(api_key)
        
        # Create adaptive system prompt
        self.system_prompt = self.create_adaptive_system_prompt()
        
        # Tone detection patterns (ordered by specificity - most specific first)
        self.tone_patterns = {
            'angry': ['angry', 'furious', 'frustrated', 'damn', 'wtf', 'terrible', 'horrible', 'worst', 'hate', 'sucks'],
            'formal': ['please', 'kindly', 'could you', 'would you', 'appreciate', 'regarding', 'sincerely', 'respectfully'],
            'urgent': ['urgent', 'immediately', 'asap', 'quickly', 'now', 'emergency', 'critical', 'hurry'],
            'confused': ['confused', 'don\'t understand', 'unclear', 'what does', 'how does', 'explain', 'clarify'],
            'grateful': ['thank', 'thanks', 'appreciate', 'grateful', 'helpful', 'awesome', 'amazing'],
            'sarcastic': ['sure', 'yeah right', 'obviously', 'totally', 'brilliant'],
            # Gen Alpha - VERY specific phrases only
            'genalpha': ['skibidi toilet', 'skibidi', 'gyat damn', 'gyat', 'sigma male', 'sigma grindset', 'only in ohio', 'goofy ahh', 'griddy', 'fanum tax', 'baby gronk', 'livvy dunne', 'garten of banban', 'unspoken rizz'],
            # Gen Z - common but distinct
            'genz': ['no cap', 'fr fr', 'bussin', 'slaps', 'lowkey', 'highkey', 'vibe check', 'slay', 'ate that', 'period', 'it\'s giving', 'main character', 'understood the assignment', 'iykyk', 'rent free'],
            # Millennial
            'millennial': ['literally', 'adulting', 'i can\'t even', 'mood', 'same', 'vibes', 'obsessed', 'iconic', 'yasss', 'goals', 'savage', 'i\'m screaming'],
            # AAVE
            'aave': ['finna', 'boujee', 'snatched', 'on fleek', 'turnt', 'clap back', 'throw shade', 'stay woke', 'periodt', 'it be like that', 'you feel me'],
            # General casual - lower priority
            'casual': ['hey', 'hi', 'sup', 'yeah', 'cool', 'lol', 'haha', 'dude'],
            'friendly': ['hello', 'good', 'nice', 'great']
        }
    
    def setup_openai_api(self, api_key: str = None):
        """Configure OpenAI API"""
        final_api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if not final_api_key:
            print("🔑 OpenAI API key not found.")
            final_api_key = input("Enter your OpenAI API key: ").strip()
        
        if not final_api_key:
            raise ValueError("API key is required to run the bot.")
        
        self.client = OpenAI(api_key=final_api_key)
        print("✅ OpenAI API configured successfully")
    
    def load_all_knowledge_bases(self):
        """Load all JSONL files into knowledge base"""
        print("\n📚 Loading knowledge bases...")
        
        for file_path in self.jsonl_files:
            if not os.path.exists(file_path):
                print(f"⚠️  File not found: {file_path}")
                continue
            
            domain = os.path.splitext(os.path.basename(file_path))[0]
            file_entries = []
            
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line_num, line in enumerate(file, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            entry = json.loads(line)
                            
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
                                    kb_entry = {
                                        'domain': domain,
                                        'question': question,
                                        'answer': answer
                                    }
                                    self.knowledge_base.append(kb_entry)
                                    file_entries.append(kb_entry)
                        
                        except json.JSONDecodeError as e:
                            print(f"⚠️  Line {line_num} in {file_path}: Invalid JSON")
                            continue
                
                self.domain_map[domain] = file_entries
                print(f"✅ Loaded {len(file_entries)} entries from {domain}")
            
            except Exception as e:
                print(f"❌ Error loading {file_path}: {e}")
        
        print(f"\n📊 Total Knowledge Base: {len(self.knowledge_base)} entries across {len(self.domain_map)} domains")
    
    def detect_tone(self, text: str) -> Dict[str, float]:
        """
        Detect tone/sentiment of user's message
        Returns tone scores with improved accuracy
        """
        text_lower = text.lower()
        tone_scores = {}
        
        # Check for exclamation marks (indicates excitement/anger)
        exclamation_count = text.count('!')
        question_count = text.count('?')
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        
        # Pattern matching for each tone with weighted scoring
        for tone, patterns in self.tone_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in text_lower:
                    # Multi-word patterns get higher weight
                    word_count = len(pattern.split())
                    score += word_count  # 2-3 word phrases count more
            tone_scores[tone] = score
        
        # Boost specific tones based on punctuation
        if exclamation_count >= 2:
            tone_scores['angry'] = tone_scores.get('angry', 0) + 2
            tone_scores['urgent'] = tone_scores.get('urgent', 0) + 1
        
        if question_count >= 2:
            tone_scores['confused'] = tone_scores.get('confused', 0) + 1
        
        if caps_ratio > 0.5 and len(text) > 10:
            tone_scores['angry'] = tone_scores.get('angry', 0) + 3
            tone_scores['urgent'] = tone_scores.get('urgent', 0) + 1
        
        # Filter out very low scores (threshold)
        tone_scores = {k: v for k, v in tone_scores.items() if v > 0}
        
        # Normalize scores
        max_score = max(tone_scores.values()) if tone_scores else 0
        if max_score > 0:
            tone_scores = {k: v / max_score for k, v in tone_scores.items()}
        
        return tone_scores
    
    def get_dominant_tone(self, tone_scores: Dict[str, float]) -> str:
        """Get the dominant tone from scores with minimum threshold"""
        if not tone_scores:
            return 'neutral'
        
        # Get max score
        max_score = max(tone_scores.values())
        
        # If max score is too low or multiple tones are equally matched, return neutral
        if max_score < 0.5:  # Threshold - only switch tone if confident
            return 'neutral'
        
        # Check if multiple tones have similar scores (ambiguous)
        high_scores = [k for k, v in tone_scores.items() if v >= max_score * 0.8]
        if len(high_scores) > 2:  # Too many tones detected
            return 'neutral'
        
        dominant_tone = max(tone_scores.items(), key=lambda x: x[1])[0]
        return dominant_tone
    
    def create_adaptive_system_prompt(self) -> str:
        """Create system prompt for tone adaptation"""
        return """You are an intelligent, adaptive AI assistant with multi-domain knowledge and mastery of various communication styles.

CORE CAPABILITIES:
- Answer questions across multiple domains (customer support, hospitality, healthcare, finance, etc.)
- Adapt your tone and style to match the user's communication style perfectly
- Speak fluently in various slang and casual language styles including the latest internet culture
- Provide accurate information from your knowledge base
- Handle both specific and general questions naturally

TONE ADAPTATION RULES:
1. ANGRY/FRUSTRATED: Be empathetic, apologetic, and solution-focused. Show understanding.
2. FORMAL: Use professional language, complete sentences, and proper business etiquette.
3. CASUAL: Be friendly, conversational, and approachable. Use contractions and simple language.
4. URGENT: Respond quickly with direct, actionable information. Skip pleasantries.
5. CONFUSED: Be patient, clear, and explanatory. Break down complex information.
6. GRATEFUL: Be warm and encouraging. Reinforce positive interaction.
7. SARCASTIC: Stay professional but acknowledge the underlying concern with empathy.
8. GEN ALPHA: Use Gen Alpha brain rot and TikTok culture slang - "skibidi", "rizz", "gyat", "sigma male", "alpha", "only in Ohio", "goofy ahh", "griddy", "fanum tax", "NPC energy", "based", "cringe", "W/L", "rizzler", "unspoken rizz", "livvy dunne rizzing up baby gronk". Embrace the chaotic, meme-heavy internet culture. Reference TikTok trends and streamers naturally.
9. GEN Z: Use Gen Z slang authentically - "fr fr", "no cap", "bussin", "slaps", "lowkey/highkey", "vibe check", "slay", "ate that", "period", "it's giving", "bestie", "main character energy", "rizz", "sus", "bet", "fam", "bruh", "ngl", "iykyk", "rent free", "understood the assignment".
10. MILLENNIAL: Use millennial expressions - "literally", "I can't even", "adulting", "mood", "same", "vibes", "obsessed", "iconic", "yasss", "goals", "af", "tbh", "omg", "irl", "savage", "dead", "I'm screaming", "this is everything".
11. AAVE (African American Vernacular English): Use AAVE authentically and respectfully - "finna", "boujee", "snatched", "on fleek", "turnt", "lit", "flex", "clap back", "throw shade", "stay woke", "fire", "dead", "tight", "pressed", "extra", "tea", "sis", "periodt", "it be like that", "you feel me", "facts".
12. NEUTRAL: Be helpful, clear, and balanced.

SLANG USAGE GUIDELINES:
- When user uses slang, MATCH their energy and slang style
- Mix slang naturally into responses - don't overdo it or force it
- Use appropriate slang for the detected communication style
- Keep it authentic and contextually appropriate
- For Gen Alpha: Embrace the chaos, reference memes, be unhinged but helpful
- For Gen Z: Be enthusiastic, use emoji concepts in text, keep it real
- For Millennial: Be self-aware, reference pop culture, add humor
- For AAVE: Be respectful, authentic, and culturally aware
- Combine slang styles when user mixes them

RESPONSE GUIDELINES:
✓ Mirror the user's energy level, formality, and slang usage
✓ Use knowledge base information when available
✓ For general questions, provide comprehensive, well-reasoned answers
✓ Be concise for casual tones, detailed for formal tones
✓ Show empathy and understanding
✓ Never break character or mention that you're adapting tone
✓ When using slang, be natural and contextually appropriate
✓ Respect cultural contexts and use language authentically
✓ For Gen Alpha: Go full brain rot mode while still being helpful

IMPORTANT:
- If the question is in your knowledge base, use that information
- If it's a general question outside your knowledge base, answer naturally with your general knowledge
- Always maintain the appropriate tone and slang style throughout your response
- Be helpful, accurate, and human-like in your responses
- Use slang to connect, not to mock or appropriate
- Gen Alpha slang is intentionally absurd - embrace it!"""
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def find_relevant_knowledge(self, user_question: str, top_k: int = 5) -> List[Dict]:
        """Find relevant knowledge base entries"""
        if not self.knowledge_base:
            return []
        
        scored_entries = []
        user_question_lower = user_question.lower()
        user_words = set(user_question_lower.split())
        
        for entry in self.knowledge_base:
            # Similarity score
            similarity = self.calculate_similarity(user_question_lower, entry['question'].lower())
            
            # Keyword overlap
            entry_words = set(entry['question'].lower().split())
            keyword_overlap = len(user_words & entry_words) / max(len(user_words), 1)
            
            # Combined score
            combined_score = (similarity * 0.6) + (keyword_overlap * 0.4)
            
            scored_entries.append({
                'entry': entry,
                'score': combined_score
            })
        
        scored_entries.sort(key=lambda x: x['score'], reverse=True)
        return [item['entry'] for item in scored_entries[:top_k]]
    
    def build_context(self, relevant_entries: List[Dict], tone: str) -> str:
        """Build context from relevant knowledge base entries"""
        if not relevant_entries or relevant_entries[0] is None:
            return ""
        
        # Only include highly relevant entries (score threshold)
        context_parts = ["RELEVANT KNOWLEDGE BASE INFORMATION:\n"]
        
        for idx, entry in enumerate(relevant_entries[:3], 1):  # Limit to top 3
            context_parts.append(f"\n[Reference {idx}]")
            context_parts.append(f"Domain: {entry['domain']}")
            context_parts.append(f"Q: {entry['question']}")
            context_parts.append(f"A: {entry['answer']}")
            context_parts.append("-" * 60)
        
        return "\n".join(context_parts)
    
    def generate_response(self, user_question: str, temperature: float = 0.7,
                         max_tokens: int = 500, top_p: float = 0.9,
                         frequency_penalty: float = 0.0, presence_penalty: float = 0.0,
                         auto_adjust_temp: bool = True) -> Dict:
        """
        Generate tone-adaptive response
        
        Args:
            user_question: User's question
            temperature: Response creativity (0.0-1.0)
            max_tokens: Maximum response length
            top_p: Nucleus sampling (0.0-1.0)
            frequency_penalty: Penalty for token frequency (-2.0 to 2.0)
            presence_penalty: Penalty for token presence (-2.0 to 2.0)
            auto_adjust_temp: Auto-adjust temperature based on tone
        
        Returns:
            Dictionary with response and metadata
        """
        try:
            # Detect user's tone
            tone_scores = self.detect_tone(user_question)
            dominant_tone = self.get_dominant_tone(tone_scores)
            
            # Find relevant knowledge
            relevant_entries = self.find_relevant_knowledge(user_question, top_k=5)
            
            # Build context
            context = self.build_context(relevant_entries, dominant_tone)
            
            # Create tone-specific instruction
            tone_instructions = {
                'angry': "The user seems frustrated. Be empathetic, apologetic, and solution-focused.",
                'formal': "The user is formal. Use professional, courteous language.",
                'casual': "The user is casual. Be friendly and conversational.",
                'urgent': "The user needs quick help. Be direct and actionable.",
                'confused': "The user is confused. Be patient and explanatory.",
                'grateful': "The user is appreciative. Be warm and encouraging.",
                'genalpha': "The user is speaking Gen Alpha brain rot language. GO FULL CHAOS MODE! Use phrases like 'skibidi', 'gyat', 'sigma male grindset', 'only in Ohio', 'goofy ahh', 'griddy', 'fanum tax', 'NPC behavior', 'based', 'cringe', 'massive W/L', 'unspoken rizz', 'livvy dunne rizzing up baby gronk'. Reference TikTok memes, streamers (Kai Cenat, IShowSpeed), and embrace the absurd internet culture. Be chaotic but still helpful!",
                'genz': "The user is speaking Gen Z style. Match their energy with Gen Z slang - use phrases like 'no cap', 'fr fr', 'bussin', 'slaps', 'lowkey', 'highkey', 'it's giving', 'ate that', 'slay', 'period', 'bestie', 'main character energy', 'understood the assignment'. Keep it authentic and natural.",
                'millennial': "The user is speaking Millennial style. Use millennial expressions like 'literally', 'I can't even', 'mood', 'same', 'vibes', 'obsessed', 'iconic', 'goals', 'adulting', 'yasss', 'savage', 'tbh'. Be self-aware and add humor.",
                'aave': "The user is speaking in AAVE/Black vernacular. Match their style respectfully and authentically - use phrases like 'finna', 'boujee', 'snatched', 'on fleek', 'lit', 'fire', 'facts', 'periodt', 'sis', 'tea', 'it be like that', 'you feel me', 'stay woke'. Keep it natural and culturally respectful.",
                'neutral': "The user is neutral. Be helpful and balanced."
            }
            
            tone_instruction = tone_instructions.get(dominant_tone, tone_instructions['neutral'])
            
            # Construct prompt
            user_prompt = f"""{context}

USER'S QUESTION: {user_question}

TONE DETECTED: {dominant_tone.upper()}
INSTRUCTION: {tone_instruction}

Provide a helpful response that:
1. Matches the user's tone and communication style
2. Uses knowledge base information if relevant
3. Answers general questions naturally if not in knowledge base
4. Is clear, accurate, and appropriately detailed

YOUR RESPONSE:"""
            
            # Adjust temperature based on tone (if auto-adjust is enabled)
            if auto_adjust_temp:
                tone_temps = {
                    'angry': 0.3,      
                    'formal': 0.4,     
                    'casual': 0.8,     
                    'urgent': 0.3,     
                    'confused': 0.5,  
                    'genalpha': 0.95,  
                    'genz': 0.9,      
                    'millennial': 0.85, 
                    'aave': 0.9,       
                    'neutral': 0.7    
                }
                adjusted_temp = tone_temps.get(dominant_tone, temperature)
            else:
                adjusted_temp = temperature
            
            # Generate response
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=adjusted_temp,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty
            )
            
            assistant_response = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens
            
            return {
                'response': assistant_response,
                'status': 'success',
                'tone_detected': dominant_tone,
                'tone_scores': tone_scores,
                'matched_entries': len(relevant_entries),
                'temperature_used': adjusted_temp,
                'tokens_used': tokens_used,
                'parameters': {
                    'temperature': adjusted_temp,
                    'max_tokens': max_tokens,
                    'top_p': top_p,
                    'frequency_penalty': frequency_penalty,
                    'presence_penalty': presence_penalty
                },
                'domains_searched': list(set([e['domain'] for e in relevant_entries])) if relevant_entries else []
            }
        
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            return {
                'response': "I apologize, but I'm experiencing technical difficulties. Please try again.",
                'status': 'error',
                'error': str(e)
            }
    
    def interactive_session(self):
        """Start interactive chat session"""
        print("\n" + "=" * 80)
        print("🤖 TONE-ADAPTIVE AI CHATBOT")
        print("=" * 80)
        print(f"📚 Knowledge Base: {len(self.knowledge_base)} entries")
        print(f"🎯 Domains: {', '.join(self.domain_map.keys())}")
        print(f"🎭 Tone Adaptation: ENABLED")
        print("\n💡 Commands:")
        print("   'quit'   - Exit chatbot")
        print("   'stats'  - View knowledge base statistics")
        print("   'params' - Adjust generation parameters")
        print("   'reset'  - Reset parameters to defaults")
        print("   'show'   - Show current parameters")
        print("-" * 80)
        
        # Default parameters
        current_params = {
            'temperature': 0.7,
            'max_tokens': 500,
            'top_p': 0.9,
            'frequency_penalty': 0.0,
            'presence_penalty': 0.0,
            'auto_adjust_temp': True  # Auto-adjust temperature based on tone
        }
        
        self.show_current_params(current_params)
        
        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'quit':
                    print("\n👋 Thank you for chatting! Goodbye!")
                    break
                
                if user_input.lower() == 'stats':
                    self.show_stats()
                    continue
                
                if user_input.lower() == 'params':
                    current_params = self.adjust_parameters(current_params)
                    continue
                
                if user_input.lower() == 'reset':
                    current_params = {
                        'temperature': 0.7,
                        'max_tokens': 500,
                        'top_p': 0.9,
                        'frequency_penalty': 0.0,
                        'presence_penalty': 0.0,
                        'auto_adjust_temp': True
                    }
                    print("✅ Parameters reset to defaults")
                    self.show_current_params(current_params)
                    continue
                
                if user_input.lower() == 'show':
                    self.show_current_params(current_params)
                    continue
                
                # Generate response
                print("\n🔄 Processing...")
                result = self.generate_response(
                    user_input,
                    temperature=current_params['temperature'],
                    max_tokens=current_params['max_tokens'],
                    top_p=current_params['top_p'],
                    frequency_penalty=current_params['frequency_penalty'],
                    presence_penalty=current_params['presence_penalty'],
                    auto_adjust_temp=current_params['auto_adjust_temp']
                )
                
                # Display response
                print(f"\n🤖 Assistant [{result['tone_detected'].upper()} tone]:")
                print(f"{result['response']}")
                
                # Show metadata (optional)
                print(f"\n📊 [Tone: {result['tone_detected']} | "
                      f"KB Matches: {result['matched_entries']} | "
                      f"Temp: {result.get('temperature_used', 'N/A')} | "
                      f"Tokens: {result.get('tokens_used', 'N/A')} | "
                      f"Domains: {', '.join(result.get('domains_searched', ['general']))}]")
            
            except KeyboardInterrupt:
                print("\n\n👋 Session ended.")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    def show_stats(self):
        """Display knowledge base statistics"""
        print("\n" + "=" * 80)
        print("📊 KNOWLEDGE BASE STATISTICS")
        print("=" * 80)
        print(f"Total Entries: {len(self.knowledge_base)}")
        print(f"\nBreakdown by Domain:")
        for domain, entries in self.domain_map.items():
            print(f"  • {domain}: {len(entries)} entries")
        print("=" * 80)
    
    def show_current_params(self, params: Dict):
        """Display current parameter settings"""
        print("\n" + "=" * 60)
        print("⚙️  CURRENT PARAMETERS")
        print("=" * 60)
        print(f"  Temperature:        {params['temperature']}")
        print(f"  Max Tokens:         {params['max_tokens']}")
        print(f"  Top P:              {params['top_p']}")
        print(f"  Frequency Penalty:  {params['frequency_penalty']}")
        print(f"  Presence Penalty:   {params['presence_penalty']}")
        print(f"  Auto-Adjust Temp:   {'ON' if params['auto_adjust_temp'] else 'OFF'}")
        print("=" * 60)
    
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
        print("  Temperature (0.0-1.0):")
        print("    → Lower (0.1-0.3): More focused, deterministic, factual")
        print("    → Medium (0.5-0.7): Balanced creativity and consistency")
        print("    → Higher (0.8-1.0): More creative, diverse, unpredictable")
        print()
        print("  Max Tokens (50-2000):")
        print("    → Controls maximum response length")
        print("    → Higher = longer responses possible")
        print()
        print("  Top P (0.0-1.0):")
        print("    → Nucleus sampling for diversity")
        print("    → Lower = more focused, Higher = more diverse")
        print()
        print("  Frequency Penalty (-2.0 to 2.0):")
        print("    → Positive = reduce repetition of words")
        print("    → Negative = allow more repetition")
        print()
        print("  Presence Penalty (-2.0 to 2.0):")
        print("    → Positive = encourage new topics")
        print("    → Negative = stick to current topics")
        print()
        print("  Auto-Adjust Temperature (yes/no):")
        print("    → If ON: Temperature auto-adjusts based on detected tone")
        print("    → If OFF: Uses your manual temperature setting")
        print("-" * 80)
        
        try:
            # Temperature
            temp_input = input(f"\nTemperature [Current: {current_params['temperature']}] (or press Enter to skip): ").strip()
            if temp_input:
                temp = float(temp_input)
                current_params['temperature'] = max(0.0, min(1.0, temp))
            
            # Max Tokens
            tokens_input = input(f"Max Tokens [Current: {current_params['max_tokens']}] (or press Enter to skip): ").strip()
            if tokens_input:
                tokens = int(tokens_input)
                current_params['max_tokens'] = max(50, min(2000, tokens))
            
            # Top P
            top_p_input = input(f"Top P [Current: {current_params['top_p']}] (or press Enter to skip): ").strip()
            if top_p_input:
                p = float(top_p_input)
                current_params['top_p'] = max(0.0, min(1.0, p))
            
            # Frequency Penalty
            freq_input = input(f"Frequency Penalty [Current: {current_params['frequency_penalty']}] (or press Enter to skip): ").strip()
            if freq_input:
                freq = float(freq_input)
                current_params['frequency_penalty'] = max(-2.0, min(2.0, freq))
            
            # Presence Penalty
            pres_input = input(f"Presence Penalty [Current: {current_params['presence_penalty']}] (or press Enter to skip): ").strip()
            if pres_input:
                pres = float(pres_input)
                current_params['presence_penalty'] = max(-2.0, min(2.0, pres))
            
            # Auto-adjust temperature
            auto_input = input(f"Auto-Adjust Temperature [Current: {'ON' if current_params['auto_adjust_temp'] else 'OFF'}] (yes/no or press Enter to skip): ").strip().lower()
            if auto_input in ['yes', 'y', 'on', '1', 'true']:
                current_params['auto_adjust_temp'] = True
            elif auto_input in ['no', 'n', 'off', '0', 'false']:
                current_params['auto_adjust_temp'] = False
            
            print("\n✅ Parameters updated successfully!")
            self.show_current_params(current_params)
        
        except ValueError:
            print("❌ Invalid input. Parameters unchanged.")
        
        return current_params


def main():
    """Main function"""
    print("🚀 Starting Tone-Adaptive Chatbot...")
    
    # List of JSONL files to load
    jsonl_files = [
        "rentomojo_faqs.jsonl",
        "hospitality.jsonl",
        "healthcare.jsonl",
        "finance.jsonl"
    ]
    
    try:
        # Initialize chatbot
        chatbot = ToneAdaptiveChatbot(jsonl_files)
        
        if len(chatbot.knowledge_base) == 0:
            print("⚠️  No knowledge base loaded. Please check your JSONL files.")
            return
        
        # Start interactive session
        chatbot.interactive_session()
    
    except Exception as e:
        print(f"❌ Failed to start chatbot: {e}")


if __name__ == "__main__":
    main()
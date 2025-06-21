import requests
import json
import time
import logging
from urllib.parse import quote
from datetime import datetime
import os
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('movie_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "7534933110:AAGT6k9Sa56LxSAhnWUOYmWDbMQpb1L4O1Q"
TMDB_API_KEY = "33dfcaee14cdda59d411e18c4d7876af"  # Get from https://www.themoviedb.org/settings/api

# API URLs
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
TMDB_BACKDROP_URL = "https://image.tmdb.org/t/p/w1280"

# Bot statistics
bot_stats = {
    'total_searches': 0,
    'successful_searches': 0,
    'start_time': datetime.now(),
    'active_users': set()
}

class MovieBot:
    def __init__(self):
        self.user_preferences = {}  # Store user preferences
        self.search_cache = {}      # Cache recent searches
        
    def get_movie_details(self, movie_name: str, year: str = None) -> Dict:
        """Enhanced movie search with detailed information"""
        try:
            # Search for the movie
            search_url = f"{TMDB_BASE_URL}/search/movie"
            params = {
                'api_key': TMDB_API_KEY,
                'query': movie_name,
                'language': 'en-US',
                'include_adult': 'false'
            }
            
            if year:
                params['year'] = year
            
            response = requests.get(search_url, params=params, timeout=10)
            data = response.json()
            
            if not data.get('results'):
                return {'success': False, 'error': 'Movie not found 😔'}
            
            # Get the best match (first result)
            movie = data['results'][0]
            movie_id = movie['id']
            
            # Get detailed movie information
            details_url = f"{TMDB_BASE_URL}/movie/{movie_id}"
            details_params = {
                'api_key': TMDB_API_KEY,
                'language': 'en-US',
                'append_to_response': 'credits,videos,keywords,similar'
            }
            
            details_response = requests.get(details_url, params=details_params, timeout=10)
            details = details_response.json()
            
            # Extract information
            poster_path = details.get('poster_path')
            backdrop_path = details.get('backdrop_path')
            
            if not poster_path:
                return {'success': False, 'error': 'No poster available for this movie 😕'}
            
            # Get cast information
            cast = details.get('credits', {}).get('cast', [])
            main_cast = [actor['name'] for actor in cast[:5]]
            
            # Get director
            crew = details.get('credits', {}).get('crew', [])
            directors = [person['name'] for person in crew if person['job'] == 'Director']
            
            # Get genres
            genres = [genre['name'] for genre in details.get('genres', [])]
            
            # Get trailer
            videos = details.get('videos', {}).get('results', [])
            trailer = None
            for video in videos:
                if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                    trailer = f"https://www.youtube.com/watch?v={video['key']}"
                    break
            
            # Get similar movies
            similar = details.get('similar', {}).get('results', [])
            similar_movies = [movie['title'] for movie in similar[:3]]
            
            return {
                'success': True,
                'title': details.get('title', 'Unknown'),
                'original_title': details.get('original_title'),
                'year': details.get('release_date', '')[:4] if details.get('release_date') else 'Unknown',
                'rating': details.get('vote_average', 0),
                'runtime': details.get('runtime', 0),
                'overview': details.get('overview', 'No description available'),
                'genres': genres,
                'cast': main_cast,
                'directors': directors,
                'poster_url': f"{TMDB_IMAGE_BASE_URL}{poster_path}",
                'backdrop_url': f"{TMDB_BACKDROP_URL}{backdrop_path}" if backdrop_path else None,
                'trailer_url': trailer,
                'similar_movies': similar_movies,
                'tmdb_id': movie_id,
                'popularity': details.get('popularity', 0)
            }
            
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Search timed out. Please try again.'}
        except Exception as e:
            logger.error(f"Error in movie search: {e}")
            return {'success': False, 'error': f'Search error: {str(e)}'}

    def get_trending_movies(self) -> List[Dict]:
        """Get trending movies"""
        try:
            url = f"{TMDB_BASE_URL}/trending/movie/week"
            params = {'api_key': TMDB_API_KEY, 'language': 'en-US'}
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            movies = []
            for movie in data.get('results', [])[:10]:
                if movie.get('poster_path'):
                    movies.append({
                        'title': movie['title'],
                        'year': movie.get('release_date', '')[:4] if movie.get('release_date') else 'Unknown',
                        'rating': movie.get('vote_average', 0),
                        'poster_url': f"{TMDB_IMAGE_BASE_URL}{movie['poster_path']}"
                    })
            
            return movies
        except Exception as e:
            logger.error(f"Error getting trending movies: {e}")
            return []

    def format_movie_info(self, movie_data: Dict) -> str:
        """Format movie information for display"""
        info = f"🎬 *{movie_data['title']}*"
        
        if movie_data.get('original_title') and movie_data['original_title'] != movie_data['title']:
            info += f" _{movie_data['original_title']}_"
        
        info += f"\n📅 *Year:* {movie_data['year']}"
        
        if movie_data['rating'] > 0:
            stars = "⭐" * int(movie_data['rating'] / 2)
            info += f"\n⭐ *Rating:* {movie_data['rating']}/10 {stars}"
        
        if movie_data.get('runtime') and movie_data['runtime'] > 0:
            hours = movie_data['runtime'] // 60
            minutes = movie_data['runtime'] % 60
            info += f"\n⏱️ *Runtime:* {hours}h {minutes}m"
        
        if movie_data.get('genres'):
            info += f"\n🎭 *Genres:* {', '.join(movie_data['genres'])}"
        
        if movie_data.get('directors'):
            info += f"\n🎬 *Director:* {', '.join(movie_data['directors'])}"
        
        if movie_data.get('cast'):
            info += f"\n👥 *Cast:* {', '.join(movie_data['cast'])}"
        
        if movie_data.get('overview'):
            overview = movie_data['overview']
            if len(overview) > 200:
                overview = overview[:200] + "..."
            info += f"\n\n📖 *Plot:*\n{overview}"
        
        return info

    def send_movie_response(self, chat_id: int, movie_data: Dict, user_prefs: Dict):
        """Send comprehensive movie response"""
        try:
            # Send poster with basic info
            caption = self.format_movie_info(movie_data)
            
            photo_response = self.send_photo(chat_id, movie_data['poster_url'], caption)
            
            if not photo_response.get('ok'):
                self.send_message(chat_id, f"❌ Couldn't send poster: {photo_response.get('description', 'Unknown error')}")
                return
            
            # Send additional options with inline keyboard
            keyboard = self.create_movie_keyboard(movie_data)
            
            options_text = "🎯 *What would you like to do?*"
            self.send_message_with_keyboard(chat_id, options_text, keyboard)
            
            # Send backdrop if available and user prefers it
            if movie_data.get('backdrop_url') and user_prefs.get('send_backdrop', True):
                time.sleep(1)  # Small delay
                self.send_photo(chat_id, movie_data['backdrop_url'], f"🖼️ Backdrop from {movie_data['title']}")
            
        except Exception as e:
            logger.error(f"Error sending movie response: {e}")
            self.send_message(chat_id, "❌ Error sending movie information")

    def create_movie_keyboard(self, movie_data: Dict):
        """Create inline keyboard for movie options"""
        keyboard = []
        
        # First row
        row1 = []
        if movie_data.get('trailer_url'):
            row1.append({"text": "🎥 Watch Trailer", "url": movie_data['trailer_url']})
        
        row1.append({"text": "📊 TMDB Page", "url": f"https://www.themoviedb.org/movie/{movie_data['tmdb_id']}"})
        
        if row1:
            keyboard.append(row1)
        
        # Second row - Similar movies
        if movie_data.get('similar_movies'):
            keyboard.append([
                {"text": "🔍 Similar Movies", "callback_data": f"similar_{movie_data['tmdb_id']}"}
            ])
        
        return {"inline_keyboard": keyboard}

    def send_message(self, chat_id: int, text: str):
        """Send text message"""
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.post(url, data=data, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {'ok': False}

    def send_message_with_keyboard(self, chat_id: int, text: str, keyboard: Dict):
        """Send message with inline keyboard"""
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
            'reply_markup': json.dumps(keyboard)
        }
        try:
            response = requests.post(url, data=data, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message with keyboard: {e}")
            return {'ok': False}

    def send_photo(self, chat_id: int, photo_url: str, caption: str = ""):
        """Send photo message"""
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        data = {
            'chat_id': chat_id,
            'photo': photo_url,
            'caption': caption,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.post(url, data=data, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            return {'ok': False}

    def handle_callback_query(self, callback_query: Dict):
        """Handle inline keyboard button presses"""
        try:
            chat_id = callback_query['message']['chat']['id']
            data = callback_query['data']
            
            if data.startswith('similar_'):
                movie_id = data.split('_')[1]
                # Get similar movies and send them
                self.send_similar_movies(chat_id, movie_id)
            
            # Answer callback query to remove loading state
            answer_url = f"{TELEGRAM_API_URL}/answerCallbackQuery"
            requests.post(answer_url, data={'callback_query_id': callback_query['id']})
            
        except Exception as e:
            logger.error(f"Error handling callback: {e}")

    def send_similar_movies(self, chat_id: int, movie_id: str):
        """Send similar movies list"""
        try:
            url = f"{TMDB_BASE_URL}/movie/{movie_id}/similar"
            params = {'api_key': TMDB_API_KEY, 'language': 'en-US'}
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('results'):
                similar_text = "🎬 *Similar Movies:*\n\n"
                for i, movie in enumerate(data['results'][:8], 1):
                    year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'Unknown'
                    rating = movie.get('vote_average', 0)
                    similar_text += f"{i}. *{movie['title']}* ({year}) ⭐{rating}/10\n"
                
                similar_text += "\n💡 _Just type any movie name to search!_"
                self.send_message(chat_id, similar_text)
            else:
                self.send_message(chat_id, "❌ No similar movies found")
                
        except Exception as e:
            logger.error(f"Error getting similar movies: {e}")
            self.send_message(chat_id, "❌ Error getting similar movies")

    def handle_message(self, message: Dict):
        """Enhanced message handler"""
        try:
            chat_id = message['chat']['id']
            user_id = message['from']['id']
            text = message.get('text', '').strip()
            user_name = message['from'].get('first_name', 'User')
            
            # Update user activity
            bot_stats['active_users'].add(user_id)
            
            # Initialize user preferences
            if user_id not in self.user_preferences:
                self.user_preferences[user_id] = {
                    'send_backdrop': True,
                    'detailed_info': True,
                    'search_count': 0
                }
            
            user_prefs = self.user_preferences[user_id]
            
            # Handle commands
            if text.startswith('/start'):
                welcome_msg = (
                    f"🎬 *Welcome to Movie Cover Bot Pro!* 🎬\n\n"
                    f"Hello {user_name}! I'm your advanced movie companion.\n\n"
                    "🔥 *What I can do:*\n"
                    "• 🎭 Find movie posters & detailed info\n"
                    "• 🎥 Get trailers and cast details\n"
                    "• 📈 Show trending movies\n"
                    "• 🔍 Suggest similar movies\n"
                    "• ⭐ Ratings, runtime, and reviews\n\n"
                    "💡 *How to use:*\n"
                    "Just type any movie name!\n"
                    "Example: `Inception` or `The Dark Knight 2008`\n\n"
                    "Try `/trending` for hot movies right now! 🔥"
                )
                self.send_message(chat_id, welcome_msg)
                
            elif text.startswith('/help'):
                help_msg = (
                    "🎬 *Movie Cover Bot Pro - Help* 🎬\n\n"
                    "🔍 *Search Commands:*\n"
                    "• Just type movie name: `Avatar`\n"
                    "• With year: `Avatar 2009`\n"
                    "• Exact match: `\"The Batman\" 2022`\n\n"
                    "📱 *Bot Commands:*\n"
                    "/start - Welcome message\n"
                    "/help - This help menu\n"
                    "/trending - Today's trending movies\n"
                    "/stats - Bot statistics\n"
                    "/settings - User preferences\n\n"
                    "🎯 *Pro Features:*\n"
                    "• High-quality posters & backdrops\n"
                    "• Cast, director, and genre info\n"
                    "• Movie trailers and ratings\n"
                    "• Similar movie suggestions\n"
                    "• Trending movies list\n\n"
                    "💡 *Tips:*\n"
                    "• Use specific titles for best results\n"
                    "• Include year for older movies\n"
                    "• Check similar movies for recommendations"
                )
                self.send_message(chat_id, help_msg)
                
            elif text.startswith('/trending'):
                self.send_message(chat_id, "🔥 Getting trending movies...")
                trending = self.get_trending_movies()
                
                if trending:
                    trending_text = "🔥 *Trending Movies This Week:*\n\n"
                    for i, movie in enumerate(trending, 1):
                        stars = "⭐" * int(movie['rating'] / 2)
                        trending_text += f"{i}. *{movie['title']}* ({movie['year']}) {stars}\n"
                    
                    trending_text += "\n💡 _Type any movie name to get details!_"
                    self.send_message(chat_id, trending_text)
                    
                    # Send poster of top trending movie
                    if trending:
                        time.sleep(1)
                        top_movie = trending[0]
                        self.send_photo(chat_id, top_movie['poster_url'], 
                                      f"🔥 #{1} Trending: {top_movie['title']} ({top_movie['year']})")
                else:
                    self.send_message(chat_id, "❌ Couldn't get trending movies right now")
                    
            elif text.startswith('/stats'):
                uptime = datetime.now() - bot_stats['start_time']
                stats_msg = (
                    "📊 *Bot Statistics:*\n\n"
                    f"🔍 Total searches: {bot_stats['total_searches']}\n"
                    f"✅ Successful: {bot_stats['successful_searches']}\n"
                    f"👥 Active users: {len(bot_stats['active_users'])}\n"
                    f"⏰ Uptime: {uptime.days} days, {uptime.seconds//3600} hours\n"
                    f"🎬 Your searches: {user_prefs['search_count']}"
                )
                self.send_message(chat_id, stats_msg)
                
            elif text.startswith('/settings'):
                settings_keyboard = {
                    "inline_keyboard": [
                        [{"text": f"🖼️ Backdrop: {'✅' if user_prefs['send_backdrop'] else '❌'}", 
                          "callback_data": "toggle_backdrop"}],
                        [{"text": f"📋 Detailed Info: {'✅' if user_prefs['detailed_info'] else '❌'}", 
                          "callback_data": "toggle_details"}]
                    ]
                }
                self.send_message_with_keyboard(chat_id, "⚙️ *Your Settings:*", settings_keyboard)
                
            elif text and not text.startswith('/'):
                # Movie search
                self.send_message(chat_id, f"🔍 Searching for '{text}'...")
                
                # Update statistics
                bot_stats['total_searches'] += 1
                user_prefs['search_count'] += 1
                
                # Parse year from text if present
                year = None
                if any(char.isdigit() for char in text):
                    words = text.split()
                    for word in words:
                        if word.isdigit() and len(word) == 4 and 1900 <= int(word) <= 2030:
                            year = word
                            text = text.replace(word, '').strip()
                            break
                
                # Search for movie
                result = self.get_movie_details(text, year)
                
                if result['success']:
                    bot_stats['successful_searches'] += 1
                    self.send_movie_response(chat_id, result, user_prefs)
                    
                    # Cache the search
                    self.search_cache[text.lower()] = result
                else:
                    self.send_message(chat_id, f"❌ {result['error']}\n\n💡 Try:\n• Different spelling\n• Adding release year\n• More specific title")
            else:
                self.send_message(chat_id, "Please send me a movie name or use /help for instructions! 🎬")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self.send_message(chat_id, "❌ Something went wrong. Please try again!")

    def get_updates(self, offset: Optional[int] = None) -> Optional[Dict]:
        """Get updates with better error handling"""
        url = f"{TELEGRAM_API_URL}/getUpdates"
        params = {'timeout': 30, 'limit': 100}
        if offset:
            params['offset'] = offset
        
        try:
            response = requests.get(url, params=params, timeout=35)
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning("Timeout getting updates")
            return None
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return None

    def run(self):
        """Main bot loop with enhanced error handling"""
        logger.info("🤖 Movie Cover Bot Pro started!")
        logger.info("🎬 Ready to serve movie lovers!")
        
        if TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
            logger.error("⚠️ TMDB API key not set! Get it from: https://www.themoviedb.org/settings/api")
            return
        
        offset = None
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            while True:
                updates = self.get_updates(offset)
                
                if updates and updates.get('ok'):
                    consecutive_errors = 0  # Reset error counter
                    
                    for update in updates['result']:
                        try:
                            if 'message' in update:
                                self.handle_message(update['message'])
                            elif 'callback_query' in update:
                                self.handle_callback_query(update['callback_query'])
                            
                            offset = update['update_id'] + 1
                            
                        except Exception as e:
                            logger.error(f"Error processing update: {e}")
                            continue
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Too many consecutive errors ({consecutive_errors}). Restarting...")
                        time.sleep(10)
                        consecutive_errors = 0
                    else:
                        time.sleep(2)
                
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"Fatal bot error: {e}")
            raise

# Run the bot
if __name__ == "__main__":
    bot = MovieBot()
    bot.run()
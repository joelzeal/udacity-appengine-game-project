# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""


"""This file contains configuration for the game API and
also the game logic. """


import endpoints
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from models import (
    StringMessage,
    NewGameForm,
    GameForm,
    MakeMoveForm,
    ScoreForms,
    GameForms,
    UserRankForm,
    UserRankForms,
    User,
    Game,
    Score
)
from utils import get_by_urlsafe, replaceCharactersInString


NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
GET_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1),)
GET_HIGH_SCORES_REQUEST = endpoints.ResourceContainer(
    number_of_results=messages.IntegerField(1, default=5),)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1),)
USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))

GET_USER_GAMES_REQUEST = endpoints.ResourceContainer(
    user_name=messages.StringField(1),)

MEMCACHE_MOVES_REMAINING = 'MOVES_REMAINING'


@endpoints.api(name='guess_the_word', version='v1')
class GuessTheWordApi(remote.Service):
    """Game API"""
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                'A User with that name already exists!')
        user = User(name=request.user_name, email=request.email)
        user.put()
        return StringMessage(message='User {} created!'.format(
            request.user_name))

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        game = Game.new_game(user.key,  request.attempts)

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        taskqueue.add(url='/tasks/cache_average_attempts')
        return game.to_form('Good luck playing Guess The Word!')

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form('Time to make a move!')
        else:
            raise endpoints.NotFoundException('Game not found!')

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            raise endpoints.BadRequestException('Illigal action: Game is already over')

        #ensure user entry is not empty is an alphanumeric
        if not request.guess.isalpha():
            raise endpoints.BadRequestException('Invalid input: Make sure your guess is alphanumeric.')

        # check if user entry is equal to the complete word or is a single word
        if len(request.guess) > 1:
            if request.guess == game.target_word:

                game_history_text = 'Guess:' + request.guess
                game_history_text += ',Result:You win'
                game.game_history.append(game_history_text)
                game.put()
                return game.to_form('You win!')

        if request.guess in game.target_missingLetters:
            if len(game.target_missingLetters) == 1:
                game.target_missingLetters.remove(request.guess)
                game.end_game(True)
                game.target_wordWithMissingLetters = replaceCharactersInString(game.target_word, game.target_missingLetters, '_')

                game_history_text = 'Guess:' + request.guess
                game_history_text += ',Result:You win'
                game.game_history.append(game_history_text)

                game.put()

                return game.to_form('You win!')
            else:
                game.target_missingLetters.remove(request.guess)
                game.target_wordWithMissingLetters = replaceCharactersInString(game.target_word, game.target_missingLetters, '_')

                game_history_text = 'Guess:' + request.guess
                game_history_text += ',Result:Right guess'
                game.game_history.append(game_history_text)

                game.put()
                return game.to_form('Right guess')
        else:
            if game.attempts_remaining < 1:
                game.end_game(False)

                game_history_text = 'Guess:' + request.guess
                game_history_text += ',Result:Game over'
                game.game_history.append(game_history_text)
                game.put()
                return game.to_form('Game over!')
            else:
                game.attempts_remaining -= 1

                game_history_text = 'Guess:' + request.guess
                game_history_text += ',Result:Wrong guess'
                game.game_history.append(game_history_text)

                game.put()
                return game.to_form('Wrong guess')

    @endpoints.method(response_message=ScoreForms,
                      path='scores',
                      name='get_scores',
                      http_method='GET')
    def get_scores(self, request):
        """Return all scores"""
        return ScoreForms(items=[score.to_form() for score in Score.query()])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      name='get_user_scores',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual User's scores"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException('A User with that name does not exist!')
        scores = Score.query(Score.user == user.key)
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(response_message=StringMessage,
                      path='games/average_attempts',
                      name='get_average_attempts_remaining',
                      http_method='GET')
    def get_average_attempts(self, request):
        """Get the cached average moves remaining"""
        return StringMessage(message=memcache.get(MEMCACHE_MOVES_REMAINING) or '')

    @staticmethod
    def _cache_average_attempts():
        """Populates memcache with the average moves remaining of Games"""
        games = Game.query(Game.game_over is False).fetch()
        if games:
            count = len(games)
            total_attempts_remaining = sum([game.attempts_remaining for game in games])
            average = float(total_attempts_remaining)/count
            memcache.set(MEMCACHE_MOVES_REMAINING,
                         'The average moves remaining is {:.2f}'.format(average))

    @endpoints.method(request_message=GET_USER_GAMES_REQUEST,
                      response_message=GameForms,
                      path='games/user/{user_name}',
                      name='get_user_games',
                      http_method='GET')
    def get_user_games(self, request):
        """Get all User's active games"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException('A User with that name does not exist!')
        games = Game.query(ancestor=user.key)
        games = games.filter(Game.game_over is False)
        return GameForms(items=[game.to_form('') for game in games])

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/cancel/{urlsafe_game_key}',
                      name='cancel_game',
                      http_method='PUT')
    def cancel_game(self, request):
        """Cancel an active game"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException('Game not found')
        else:
            if game.game_over:
                raise endpoints.BadRequestException('Illigal action: Game is already over')
            else:
                game.game_over = True
                game.cancelled = True
                game.put()
                return StringMessage(message='Game has been cancelled.')

    @endpoints.method(request_message=GET_HIGH_SCORES_REQUEST,
                      response_message=ScoreForms,
                      path='game/high_scores/{number_of_results}',
                      name='get_high_scores',
                      http_method='GET')
    def get_high_scores(self, request):
        """Get high scores"""
        # score with fewer attempts has a higher ranking. eg. A score of 2 attempts is higher
        # a score with 5 attempts
        scores = Score.query(Score.won is True).order(Score.guesses).fetch(request.number_of_results)
        if not scores:
            raise endpoints.NotFoundException('No scores found.')
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/gamehistory/{urlsafe_game_key}',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self, request):
        """Get game history"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form('Game history')
        else:
            raise endpoints.NotFoundException('Game not found!')

    @endpoints.method(response_message=UserRankForms,
                      path='users/ranking',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        """Get game history"""
        # user rankings
        userRanking = UserRankForms()

        # get  all users
        users = User.query().fetch()

        # Get user scores and perform calculation
        for user in users:
            user_scores = Score.query(ancestor=user.key)
            user_scores.count()
            won = 0.0
            lost = 0
            gamecount = 0
            if user_scores:
                for score in user_scores:
                    gamecount += 1
                    if score.won is True:
                        won += 1
                    else:
                        lost += 1
                # perform ranking calculation
                if gamecount > 0:
                    performance = won/gamecount
                else:
                    performance = -1.0  # -1 means user has not completed any games

                userRanking.items.append(UserRankForm(user_name=user.name, performance_indicator=performance))

        # return reverse sorted user ranks
        # reverseOrderUserRanking.items = reversed(sorted(userRanking.items))
        return userRanking
        # return userRanking

api = endpoints.api_server([GuessTheWordApi])

"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb
from utils import replaceCharactersInString


class User(ndb.Model):
    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()


class Game(ndb.Model):
    """Game object"""
    target_missingLetters = ndb.StringProperty(repeated=True)
    target_word = ndb.StringProperty(required=True)
    target_wordWithMissingLetters = ndb.StringProperty(required=True)
    attempts_allowed = ndb.IntegerProperty(required=True)
    attempts_remaining = ndb.IntegerProperty(required=True, default=5)
    game_over = ndb.BooleanProperty(required=True, default=False)
    cancelled = ndb.BooleanProperty(default=False)
    game_history = ndb.StringProperty(repeated=True)
    # user = ndb.KeyProperty(required=True, kind='User')

    @classmethod
    def new_game(cls, user,  attempts):
        """Creates and returns a new game"""

        wordStore = ["ability", "about", "above", "absolute", "accessible", "accommodation",
             "accounting", "beautiful", "bookstore", "calculator", "clever", "engaged",
             "engineer", "enough", "handsome", "refrigerator", "opposite", "socks",
             "interested", "strawberry", "backgammon", "anniversary", "confused",
             "dangerous", "entertainment", "exhausted", "impossible", "overweight",
             "temperature", "vacation", "scissors", "accommodation", "appointment",
             "decrease", "development", "earthquake", "environment", "brand",
             "environment", "necessary", "luggage", "responsible", "ambassador",
             "circumstance", "congratulate", "frequent", ]
        randomIndex = random.randint(0, len(wordStore))
        wordToGuess = wordStore[randomIndex]
        lengthOfWord = len(wordToGuess)
        charactersToGuess = random.sample(list(wordToGuess), lengthOfWord/2)
        # wordWithMissingLetters = wordStore[randomIndex]

        # create instance of game
        game = Game(target_missingLetters=charactersToGuess,
                    target_word=''.join(wordToGuess),
                    target_wordWithMissingLetters=replaceCharactersInString(wordStore[randomIndex], charactersToGuess, '_'),
                    attempts_allowed=attempts,
                    attempts_remaining=attempts,
                    game_over=False,
                    parent=user)
        game.put()
        return game

    def to_form(self, message):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.key.parent().get().name
        form.attempts_remaining = self.attempts_remaining
        form.game_over = self.game_over
        form.word_missing_letters = self.target_wordWithMissingLetters
        form.message = message
        form.game_history = GameHistoryForm(histories=[hist for hist in self.game_history])
        return form

# return ScoreForms(items=[score.to_form() for score in Score.query()])

    def end_game(self, won=False):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        self.game_over = True
        self.put()
        # Add the game to the score 'board'
        # user=self.key.parent(),
        score = Score(date=date.today(), won=won, user=self.key.parent(),
                      guesses=self.attempts_allowed - self.attempts_remaining, parent=self.key.parent())
        score.put()


class Score(ndb.Model):
    """Score object"""
    user = ndb.KeyProperty(required=True, kind='User')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True)
    guesses = ndb.IntegerProperty(required=True)

    def to_form(self):
        return ScoreForm(user_name=self.key.parent().get().name, won=self.won,
                         date=str(self.date), guesses=self.guesses)


class GameHistoryForm(messages.Message):
    """Game history list form"""
    histories = messages.StringField(1, repeated=True)


class GameForm(messages.Message):
    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_remaining = messages.IntegerField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    message = messages.StringField(4, required=True)
    user_name = messages.StringField(5, required=True)
    word_missing_letters = messages.StringField(6)
    game_history = messages.MessageField(GameHistoryForm, 7)


class NewGameForm(messages.Message):
    """Used to create a new game"""
    user_name = messages.StringField(1, required=True)
    attempts = messages.IntegerField(4, default=5)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    guess = messages.StringField(1, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information"""
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    won = messages.BooleanField(3, required=True)
    guesses = messages.IntegerField(4, required=True)


class UserRankForm(messages.Message):
    """Used to display user rankings"""
    user_name = messages.StringField(1, required=True)
    performance_indicator = messages.FloatField(2, required=True)


class UserRankForms(messages.Message):
    """Return multiple User ranking forms"""
    items = messages.MessageField(UserRankForm, 1, repeated=True)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class GameForms(messages.Message):
    """Return multiple games"""
    items = messages.MessageField(GameForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage -- outbound (single) string message"""
    message = messages.StringField(1, required=True)

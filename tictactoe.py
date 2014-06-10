import jinja2
import os
import webapp2
from google.appengine.api import channel
from google.appengine.api import users
from google.appengine.ext import ndb

class Game(ndb.Model):
  """All the data we store for a game"""
  userX = ndb.UserProperty()
  userO = ndb.UserProperty()
  board = ndb.StringProperty()
  moveX = ndb.BooleanProperty()
  winner = ndb.StringProperty()
  winning_board = ndb.StringProperty()
  key_name = ndb.StringProperty()

class MainPage(webapp2.RequestHandler):
  """This page is responsible for showing the game UI. It may also
  create a new game or add the currently-logged in user to a game."""

  def get(self):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.uri))
      return
    game_key = self.request.get('gamekey')
    

    game = None
    if not game_key:
      # If no game was specified, create a new game and make this user
      # the 'X' player.
      game_key = user.user_id()
      game = Game(key_name = game_key,
                  userX = user,
                  moveX = True,
                  board = '         ')
      game.put()
      print("starting game...."+game_key)
    else:
      game = Game.get_by_key_name(game_key)
      if not game.userO and game.userX != user:
        # If this game has no 'O' player, then make the current user
        # the 'O' player.
        game.userO = user
        game.put()

    token = channel.create_channel(user.user_id() + game_key)
    template_values = {'token': token,
                       'me': user.user_id(),
                       'game_key': game_key
                       }
    template = jinja_environment.get_template('index.html')
    self.response.out.write(template.render(template_values))

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))
app = webapp2.WSGIApplication([('/', MainPage)],
                              debug=True)


class MovePage(webapp2.RequestHandler):

  def post(self):
    game = GameFromRequest(self.request).get_game()
    user = users.get_current_user()
    if game and user:
      id = int(self.request.get('i'))
      GameUpdater(game).make_move(id, user)

class GameFromRequest():
  game = None;

  def __init__(self, request):
    user = users.get_current_user()
    game_key = request.get('gamekey')
    if user and game_key:
      self.game = Game.get_by_key_name(game_key)

  def get_game(self):
    return self.game

class GameUpdater():
  """Creates an object to store the game's state, and handles validating moves
  and broadcasting updates to the game."""
  game = None

  def __init__(self, game):
    self.game = game

  def get_game_message(self):
    # The gameUpdate object is sent to the client to render the state of a game.
    gameUpdate = {
      'board': self.game.board,
      'userX': self.game.userX.user_id(),
      'userO': '' if not self.game.userO else self.game.userO.user_id(),
      'moveX': self.game.moveX,
      'winner': self.game.winner,
      'winningBoard': self.game.winning_board
    }
    return simplejson.dumps(gameUpdate)

  def send_update(self):
    message = self.get_game_message()
    channel.send_message(self.game.userX.user_id() + self.game.key().name(),
message)
    if self.game.userO:
      channel.send_message(self.game.userO.user_id() + self.game.key().name(),
message)

  def check_win(self):
    if self.game.moveX:
      # O just moved, check for O wins
      wins = Wins().o_wins
      potential_winner = self.game.userO.user_id()
    else:
      # X just moved, check for X wins
      wins = Wins().x_wins
      potential_winner = self.game.userX.user_id()

    for win in wins:
      if win.match(self.game.board):
        self.game.winner = potential_winner
        self.game.winning_board = win.pattern
        return

  def make_move(self, position, user):
    if position >= 0 and user == self.game.userX or user == self.game.userO:
      if self.game.moveX == (user == self.game.userX):
        boardList = list(self.game.board)
        if (boardList[position] == ' '):
          boardList[position] = 'X' if self.game.moveX else 'O'
          self.game.board = "".join(boardList)
          self.game.moveX = not self.game.moveX
          self.check_win()
          self.game.put()
          self.send_update()
          return
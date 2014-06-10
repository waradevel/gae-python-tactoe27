"""Channel Tic Tac Toe  Python 2.7

This module demonstrates the App Engine Channel API by implementing a
simple tic-tac-toe game.
"""

import datetime
import logging
import os
import random
import re
import json
from google.appengine.api import channel
from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class Game(ndb.Model):
  """All the data we store for a game"""
  userX = ndb.UserProperty()
  userO = ndb.UserProperty()
  board = ndb.StringProperty(indexed=False)
  moveX = ndb.BooleanProperty()
  winner = ndb.StringProperty(indexed=False)
  winning_board = ndb.StringProperty(indexed=False)
  

class Wins():
  x_win_patterns = ['XXX......',
                    '...XXX...',
                    '......XXX',
                    'X..X..X..',
                    '.X..X..X.',
                    '..X..X..X',
                    'X...X...X',
                    '..X.X.X..']

  o_win_patterns = map(lambda s: s.replace('X','O'), x_win_patterns)
  
  x_wins = map(lambda s: re.compile(s), x_win_patterns)
  o_wins = map(lambda s: re.compile(s), o_win_patterns)


class GameUpdater():
  game = None

  def __init__(self, game):
    self.game = game

  def get_game_message(self):
    gameUpdate = {
      'board': self.game.board,
      'userX': self.game.userX.user_id(),
      'userO': '' if not self.game.userO else self.game.userO.user_id(),
      'moveX': self.game.moveX,
      'winner': self.game.winner,
      'winningBoard': self.game.winning_board
    }
    return json.dumps(gameUpdate)

  def send_update(self):
    message = self.get_game_message()
    #channel.send_message(self.game.userX.user_id() + self.game.key().id_or_name(), message)
    channel.send_message(self.game.userX.user_id() + self.game.key.id(), message)
    if self.game.userO:
      #channel.send_message(self.game.userO.user_id() + self.game.key().id_or_name(), message)
      channel.send_message(self.game.userO.user_id() + self.game.key.id(), message)

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


class GameFromRequest():
  game = None;

  def __init__(self, request):
    user = users.get_current_user()
    game_key = request.get('g')
    if user and game_key:
      self.game = Game.get_by_id(game_key)

  def get_game(self):
    return self.game


class MovePage(webapp2.RequestHandler):

  def post(self):
    game = GameFromRequest(self.request).get_game()
    user = users.get_current_user()
    if game and user:
      id = int(self.request.get('i'))
      GameUpdater(game).make_move(id, user)


class OpenedPage(webapp2.RequestHandler):
  def post(self):
    game = GameFromRequest(self.request).get_game()
    GameUpdater(game).send_update()


class MainPage(webapp2.RequestHandler):
  """The main UI page, renders the 'index.html' template."""

  def get(self):
    """Renders the main page. When this page is shown, we create a new
    channel to push asynchronous updates to the client."""
    user = users.get_current_user()
    game_key = self.request.get('g')
    game = None
    if user:
      if not game_key:
        game_key = user.user_id()
        game = Game(id = game_key,
                    userX = user,
                    moveX = True,
                    board = '         ')
        game.put()
      else:
        game = Game.get_by_id(game_key)
        if not game.userO:
          game.userO = user
          game.put()

      game_link = 'http://localhost:8080/?g=' + game_key

      if game:
        token = channel.create_channel(user.user_id() + game_key)
        template_values = {'token': token,
                           'me': user.user_id(),
                           'game_key': game_key,
                           'game_link': game_link,
                           'initial_message': GameUpdater(game).get_game_message()
                          }
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

      else:
        self.response.out.write('No such game')
    else:
      self.redirect(users.create_login_url(self.request.uri))




application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/opened', OpenedPage),
    ('/move', MovePage)], debug=True)
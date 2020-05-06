#!/usr/bin/python
#-*- coding: utf-8 -*-

import random
from messages import diz


class GameError(Exception):
    pass


class StateError(GameError):
    pass


class NoWerewolf(GameError):
    pass


class NotAliveError(GameError):
    pass


class WrongPlayerNumberError(GameError):
    pass


class UnrecognizedRole(GameError):
    pass


class MoreThanOneWorP(GameError):
    pass


class WrongNumberPlayers(GameError):
    pass


class Role:
    def __init__(self, name, good, special):
        self.name = name
        self.good = good
        self.special = special

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


peasant = Role("Contadino", True, False)
werewolf = Role("werewolf", False, False)
watcher = Role("watcher", True, True)
protector = Role("protector", True, True)
werewolf_son = Role("son", True, True)


W_TIE = 0
W_GOOD = 1
W_BAD = 2


def stateName(state, language):
    if state in diz:
        return diz[state][language]
    else:
        return "ERROR"


def sideName(side, language):
    if side == W_TIE:
        return diz["tied_game"][language]
    elif side == W_GOOD:
        return diz["good_won"][language]
    elif side == W_BAD:
        return diz["bad_won"][language]
    else:
        return "ERROR"


def check_roles(rolestring):
    if len(rolestring.split("v")) > 2 or len(rolestring.split("p")) > 2:
        raise MoreThanOneWorP
    if "l" not in rolestring:
        raise NoWerewolf


def ch2role(c):
    """Role translation"""
    if c == "c":
        return peasant
    elif c == "l":
        return werewolf
    elif c == "v":
        return watcher
    elif c == "p":
        return protector
    elif c == "f":
        return werewolf_son
    else:
        raise UnrecognizedRole


class DefineGame:
    """Define Game from bot questions"""
    def __init__(self):
        self.stato = "players"
        self.n_players = None
        self.n_wolves = None
        self.n_watcher = None
        self.n_protector = None
        self.n_son = None

    def set_players(self, n):
        self.n_players = n
        self.stato = "wolf"

    def set_wolves(self, n):
        self.n_wolves = n
        self.stato = "watcher"

    def set_watcher(self, n):
        self.n_watcher = n
        self.stato = "protector"

    def set_protector(self, n):
        self.n_protector = n
        self.stato = "son"

    def set_son(self, n):
        self.n_son = n

    def set_state(self, state):
        self.stato = state



class Game:
    """Game class"""
    def __init__(self, rolelist):
        self.rolelist = rolelist
        self.turn = 0
        self.state = "PRE"
        self.special = {'werewolf': False,
                        'watcher': False if watcher in rolelist else True,
                        'protector': False if protector in rolelist else True}
        self.son_state = False
        self.players = []

    @staticmethod
    def from_rolestring(rolestring):
        """Initialize Game given list of roles"""
        check_roles(rolestring)
        rolelist = []
        for c in rolestring:
            r = ch2role(c)
            rolelist.append(r)
        return Game(rolelist)

    @staticmethod
    def from_questions(n_players, n_wolves, n_watcher, n_protector, n_son):
        """Initialize Game given players, werewolves, watchers, protectors and sons numbers"""
        rolelist = [werewolf] * n_wolves
        rolelist += [watcher] * n_watcher
        rolelist += [protector] * n_protector
        rolelist += [werewolf_son] * n_son
        n_contadini = n_players - len(rolelist)
        if n_contadini < 0:
            raise WrongNumberPlayers
        rolelist += [peasant] * n_contadini
        return Game(rolelist)

    def setPlayers(self, players):
        """Give roles to players"""
        if len(players) != len(self.rolelist):
            raise WrongPlayerNumberError

        random.shuffle(self.rolelist)

        for i, p in enumerate(players):
            p.role = self.rolelist[i]

        self.state = "RUOLI_ASSEGNATI"

    def alivePlayers(self):
        return [p for p in self.players if p.alive]

    def goodPlayers(self):
        return [p for p in self.players if (p.alive and p.role.good)]

    def badPlayers(self):
        return [p for p in self.players if (p.alive and (not p.role.good))]

    def wolves(self):
        return [p for p in self.players if (p.alive and p.role == werewolf)]

    def watcher(self):
        return [p for p in self.players if (p.alive and p.role == watcher)]

    def protector(self):
        return [p for p in self.players if (p.alive and p.role == protector)]

    def checkEnd(self):
        """Check if the game end"""
        if len(self.alivePlayers()) == 0:
            self.state = "FINISH"
            self.win = W_TIE
            return
        if len(self.goodPlayers()) == 0:
            self.state = "FINISH"
            self.win = W_BAD
            return
        if len(self.badPlayers()) == 0:
            self.state = "FINISH"
            self.win = W_GOOD

    def euthanise(self, toe):
        """Delete one player"""
        self.players[toe].alive = False
        self.players[toe].choice = None
        self.checkEnd()

    def inputNight(self, results):
        """Night step"""
        if self.state != "NIGHT_END":
            raise StateError

        killed_now = []
        out = {}

        tp = None
        if 'toprotect' in results:
            tp = results['toprotect']

            if not self.players[tp].alive:
                raise NotAliveError

        if 'tomurder' in results:
            tm = results['tomurder'][0]
            if tm is not None:
                if not self.players[tm].alive:
                    raise NotAliveError
                elif tp != tm and self.players[tm].role != werewolf_son:
                    killed_now.append(tm)
                elif self.players[tm].role == werewolf_son:
                    self.son_state = True
                    self.players[tm].role = werewolf

            out['killed_now'] = killed_now

        if 'toview' in results:
            tv = results['toview']
            out['viewed'] = self.players[tv].role.good

            if not self.players[tv].alive:
                raise NotAliveError

        for tokill in killed_now:
            self.players[tokill].alive = False

        self.state = "DAY"

        self.checkEnd()

        return out

    def inputDay(self, voted, n_veggenti, n_protettori):
        """Day syep"""
        if not self.players[voted].alive:
            raise NotAliveError

        self.players[voted].alive = False

        self.state = "NIGHT"
        self.special['watcher'] = False if n_veggenti >= 1 else True
        self.special['protector'] = False if n_protettori >= 1 else True

        self.checkEnd()

    def recompute_player_index(self):
        """Recompute players index"""
        for i, p in enumerate(self.players):
            p.index = i
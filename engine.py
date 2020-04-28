#!/usr/bin/python
# -*- coding: utf-8 -*-

import random


class GameError(Exception):
    pass


class StateError(GameError):
    pass


class NotAliveError(GameError):
    pass


class WrongPlayerNumberError(GameError):
    pass


class UnrecognizedRole(GameError):
    pass


class MoreThanOneWorP(GameError):
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


contadino = Role("Contadino", True, False)
lupo = Role("Lupo", False, False)
veggente = Role("Veggente", True, True)
protettore = Role("Protettore", True, True)
figlio_del_lupo = Role("Figlio del Lupo", True, True)


def ch2role(c):
    """Role translation"""
    if c == "c":
        return contadino
    elif c == "l":
        return lupo
    elif c == "v":
        return veggente
    elif c == "p":
        return protettore
    elif c == "f":
        return figlio_del_lupo
    else:
        raise UnrecognizedRole


NIGHT = 0
NIGHT_END = 0.5
DAY = 1
DAY_END = 3
FINISH = -1
PRE = -2
RUOLI_ASSEGNATI = -3

W_TIE = 0
W_GOOD = 1
W_BAD = 2


def stateName(state):
    if state == NIGHT:
        return "NOTTE"
    elif state == NIGHT_END:
        return "NOTTE CONCLUSA"
    elif state == DAY:
        return "GIORNO"
    elif state == DAY_END:
        return "GIORNO CONCLUSA"
    elif state == PRE:
        return "PRE"
    elif state == FINISH:
        return "PARTITA CONCLUSA"
    elif state == RUOLI_ASSEGNATI:
        return "conto alla rovescia per la notte..."
    else:
        return "ERRORE"


def sideName(side):
    if side == W_TIE:
        return "PARITÀ ⚖️"
    elif side == W_GOOD:
        return "I BUONI vincono! 👩🏻‍🌾 👨🏻‍🌾"
    elif side == W_BAD:
        return "I LUPI vincono! 🐺"
    else:
        return "ERRORE"


class Game:
    """Game class"""
    def __init__(self, rolestring):
        self.rolelist = []
        self.check_roles(rolestring)
        for c in rolestring:
            r = ch2role(c)
            self.rolelist.append(r)

        self.turn = 0
        self.state = PRE
        self.stato_lupi = False
        self.stato_veggente = False if "v" in rolestring else True
        self.stato_protettore = False if "p" in rolestring else True
        self.figlio_del_lupo = False
        self.players = []

    def check_roles(self, rolestring):
        if len(rolestring.split("v")) > 2 or len(rolestring.split("p")) > 2:
            raise MoreThanOneWorP

    def setPlayers(self, players):
        """Give roles to players"""
        if len(players) != len(self.rolelist):
            raise WrongPlayerNumberError

        random.shuffle(self.rolelist)

        for i, p in enumerate(players):
            p.role = self.rolelist[i]

        self.state = RUOLI_ASSEGNATI

    def alivePlayers(self):
        return [p for p in self.players if p.alive]

    def goodPlayers(self):
        return [p for p in self.players if (p.alive and p.role.good)]

    def badPlayers(self):
        return [p for p in self.players if (p.alive and (not p.role.good))]

    def wolves(self):
        return [p for p in self.players if (p.alive and p.role == lupo)]

    def watcher(self):
        return [p for p in self.players if (p.alive and p.role == veggente)]

    def protector(self):
        return [p for p in self.players if (p.alive and p.role == protettore)]

    def checkEnd(self):
        """Check if the game end"""
        if len(self.alivePlayers()) == 0:
            self.state = FINISH
            self.win = W_TIE
            return
        if len(self.goodPlayers()) == 0:
            self.state = FINISH
            self.win = W_BAD
            return
        if len(self.badPlayers()) == 0:
            self.state = FINISH
            self.win = W_GOOD

    def euthanise(self, toe):
        """Delete one player"""
        self.players[toe].alive = False
        self.players[toe].choice = None
        self.checkEnd()

    def inputNight(self, results):
        """Night step"""
        if self.state != NIGHT_END:
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
                elif tp != tm and self.players[tm].role != figlio_del_lupo:
                    killed_now.append(tm)
                elif self.players[tm].role == figlio_del_lupo:
                    self.figlio_del_lupo = True
                    self.players[tm].role = lupo

            out['killed_now'] = killed_now

        if 'toview' in results:
            tv = results['toview']
            out['viewed'] = self.players[tv].role.good

            if not self.players[tv].alive:
                raise NotAliveError

        for tokill in killed_now:
            self.players[tokill].alive = False

        self.state = DAY

        self.checkEnd()

        return out

    def inputDay(self, voted, n_veggenti, n_protettori):
        """Day syep"""
        if not self.players[voted].alive:
            raise NotAliveError

        self.players[voted].alive = False

        self.state = NIGHT
        self.stato_veggente = False if n_veggenti >= 1 else True
        self.stato_protettore = False if n_protettori >= 1 else True

        self.checkEnd()

    def recompute_player_index(self):
        """Recompute players index"""
        for i, p in enumerate(self.players):
            p.index = i
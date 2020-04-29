# !/usr/local/bin/python
# -*- coding: utf-8 -*-


import engine
from engine import RUOLI_ASSEGNATI, NIGHT_END, NIGHT, DAY, DAY_END, PRE, FINISH

import requests
import random
import time

import sys
from logger.defaults import WithLogging
from messages import diz

authf = open('../lupus_api', 'r')  # token bot

auth = authf.read().strip()
authf.close()


class StatusNotOk(Exception):
    pass


class Chat:
    def __init__(self, info):
        if 'first_name' in info:
            self.name = info['first_name']
        else:
            self.name = info['title']
        self.game = None
        self.language = "it"
        self.id = info['id']


class Player:
    def __init__(self, chat_id, user, i):
        self.chat_id = chat_id
        self.name = user['first_name'] if 'last_name' not in user else user['first_name'] + " " + user['last_name']
        self.index = i
        self.alive = True
        self.role = None
        self.choice = None


class LupusBot(WithLogging):
    def __init__(self):
        self.updates = []
        self.groupchats = {}
        self.lastid = 0

    def exprint(self, e):
        # turns out some exceptions are so brutal
        # they throw an exception when you try to print them.

        self.logger.debug("Exception encountered.")
        try:
            self.logger.debug(e)
        except:
            self.logger.debug("Error printing exception.")

    def safe_request(self, http, params, files=None):
        # run a requests.get but catching exceptions.
        # params and files are the usual requests.get arguments, http is the url
        # returns the request object, None if there were errors.

        try:
            if files:
                r = requests.get(http, params=params, files=files, timeout=2)
            else:
                r = requests.get(http, params=params, timeout=2)
            if r.status_code != 200:
                raise StatusNotOk
        except requests.exceptions.RequestException as e:
            self.exprint(e)
            return None
        except StatusNotOk:

            self.logger.warning("HTTP error %d" % r.status_code)

            self.logger.warning(r.text)
            self.logger.warning(r.url)

            return None
        except:
            self.logger.warning("Unexpected error:", sys.exc_info()[0])

            return None

        return r

    def get_messages(self):
        http = "https://api.telegram.org/bot%s/getUpdates" % auth + "?offset=%d" % self.lastid

        r = self.safe_request(http, {})

        if r is None:
            return

        toadd = r.json()[u'result']

        if len(toadd) == 0:
            return

        self.lastid = int(toadd[-1][u'update_id']) + 1

        self.updates = self.updates + toadd
        self.logger.info("New %d updates" % len(toadd))

        for u in toadd:
            if 'message' in u:
                cht = u['message']['chat']
                if not cht['id'] in self.groupchats:
                    CH = Chat(cht)
                    self.groupchats[cht['id']] = CH

                    self.logger.info("New chat detected! id %s name %s" % (CH.id, CH.name))

    def start_game(self, gpc):
        """Start a new game"""

        self.groupchats[gpc].game.setPlayers(self.groupchats[gpc].game.players)

        self.send_message(gpc, diz["start_game"][self.groupchats[gpc].language])

        time.sleep(3)
        for player in self.groupchats[gpc].game.players:
            self.send_message(player.chat_id, diz["role_is"][self.groupchats[gpc].language] % (
                diz[str(player.role)][self.groupchats[gpc].language]))

    def send_message(self, chat_id, message, replyto=None):
        """
        Send message
        :param chat_id: chat id
        :param message: full text message
        :param replyto: message id to reply to
        :return:
        """
        try:
            self.logger.debug("writing to chat", chat_id)
        except KeyError:
            self.logger.warning("ERROR: not in chat")
            return
        self.logger.debug("BODY:", message.split('\n')[0])

        try:
            decotex = str(message, "utf-8")
        except TypeError:
            decotex = message

        args = {'chat_id': chat_id, 'text': decotex}

        if replyto:
            args['reply_to_message_id'] = replyto
        http = "https://api.telegram.org/bot%s/sendMessage" % auth

        self.safe_request(http, args)

    def process_update(self, u, gpc=None):
        """Run commands based on received messages"""
        if 'message' in u:
            m = u['message']
            mm_strip = m['text'][1:].strip() if ('text' in m) and (m['text'][0] in ["/", "@"]) else None
            if mm_strip is not None and m['text'][0] == "/":
                command = mm_strip.split("@")
                if len(command) == 1 or (command[1] == "Lupus_paccatori_bot"):
                    self.run_command(command[0], m, 'title' in m['chat'])
            elif gpc is not None and mm_strip is not None:  # message for wolves
                recipient = mm_strip.split(" ")[0]
                sender = m['from']['id']
                if recipient == "w" and sender in [player.chat_id for player in self.groupchats[gpc].game.wolves()]:
                    for players in self.groupchats[gpc].game.wolves():
                        if players.chat_id != sender:
                            self.send_message(players.chat_id, str(m['from']['first_name'] + ":" + m['text'][2:]))

    def stop_game(self, chat):
        """Stop game, delete chat"""

        self.groupchats[chat].game = None

    def run_command(self, command, m, isgroup):
        """
        Run commands
        :param command: Command to execute
        :param m: full dict message
        :param isgroup: whether the message is written in a group or a chat
        :return:
        """
        self.logger.info("Executing command %s" % command)

        chat_id = m['chat']['id']

        message_id = m['message_id']

        comw = command.split()

        if comw[0] == "start":  # start a new game
            if not isgroup:

                self.send_message(chat_id, diz["command_in_group"][self.groupchats[chat_id].language], message_id)
            elif self.groupchats[chat_id].game:
                self.send_message(chat_id, diz["game_running"][self.groupchats[chat_id].language], message_id)
            elif len(comw) < 2:
                self.send_message(chat_id, diz["roles_missing"][self.groupchats[chat_id].language], message_id)
            else:
                try:
                    self.groupchats[chat_id].game = engine.Game(comw[1].lower().strip())
                    self.send_message(chat_id, diz["new_game"][self.groupchats[chat_id].language], message_id)

                except engine.UnrecognizedRole:
                    self.send_message(chat_id, diz["wrong_role"][self.groupchats[chat_id].language], message_id)
                except engine.MoreThanOneWorP:
                    self.send_message(chat_id, diz["wrong_wp_number"][self.groupchats[chat_id].language], message_id)

        elif comw[0] == "in":  # add a new player
            if not isgroup:
                pass
            else:
                if not self.groupchats[chat_id].game:
                    self.send_message(chat_id, diz["no_game"][self.groupchats[chat_id].language], message_id)
                else:
                    if self.groupchats[chat_id].game.state != PRE:
                        self.send_message(chat_id, diz["late_player"][self.groupchats[chat_id].language], message_id)
                    else:
                        sender = m['from']['id']

                        for player in self.groupchats[chat_id].game.players:
                            if player.chat_id == sender:
                                self.send_message(chat_id, diz["already_confirmed"][self.groupchats[chat_id].language],
                                                  message_id)
                                return

                        if len(self.groupchats[chat_id].game.players) < len(self.groupchats[chat_id].game.rolelist):
                            self.groupchats[chat_id].game.players.append(Player(sender, m['from'],
                                                                                len(self.groupchats[
                                                                                        chat_id].game.players)))
                            self.send_message(chat_id, diz["insert"][self.groupchats[chat_id].language] % (
                                len(self.groupchats[chat_id].game.players),
                                len(self.groupchats[chat_id].game.rolelist)),
                                              message_id)
                            if len(self.groupchats[chat_id].game.players) == len(
                                    self.groupchats[chat_id].game.rolelist):
                                self.start_game(chat_id)
                        else:
                            self.send_message(chat_id, diz["max_players"][self.groupchats[chat_id].language],
                                              message_id)

        elif comw[0] == "stop":  # stop game
            self.send_message(chat_id, diz["stop"][self.groupchats[chat_id].language], message_id)

        elif comw[0] == "stopstop":  # stop game for real!
            if not isgroup:
                delete = False
                for gpc in self.groupchats:
                    player = self.get_player(chat_id, gpc)
                    delete = True if player is not None else False
                    if self.groupchats[gpc].game.state != PRE:
                        self.send_message(chat_id, diz["kill_himself"][self.groupchats[gpc].language], message_id)
                        self.groupchats[gpc].game.euthanise(player.index)
                        self.send_message(gpc, diz["killed"][self.groupchats[gpc].language] % player.name)
                        break
                    else:
                        self.send_message(chat_id, diz["left_game"][self.groupchats[gpc].language], message_id)
                        del self.groupchats[gpc].game.players[player.index]
                        self.groupchats[gpc].game.recompute_player_index()
                        self.send_message(gpc, diz["left"][self.groupchats[gpc].language] % player.name, message_id)
                        break

                if not delete:
                    self.send_message(chat_id, diz["no_present"][self.groupchats[chat_id].language], message_id)

            else:
                if self.groupchats[chat_id].game is None:
                    self.send_message(chat_id, diz["nothing_to_stop"][self.groupchats[chat_id].language], message_id)
                else:
                    try:
                        for p in self.groupchats[chat_id].game.players:
                            self.send_message(p.chat_id, diz["stopped"][self.groupchats[chat_id].language], message_id)
                    except ValueError:
                        pass
                    self.stop_game(chat_id)
                    self.send_message(chat_id, diz["finish"][self.groupchats[chat_id].language], message_id)

        elif comw[0] == "info":  # info
            if isgroup:
                if self.groupchats[chat_id].game:
                    if self.groupchats[chat_id].game.state == PRE:
                        self.send_message(chat_id, diz["waiting"][self.groupchats[chat_id].language], message_id)

                    elif self.groupchats[chat_id].game.state == NIGHT:
                        st = ""
                        if not self.groupchats[chat_id].game.stato_lupi:
                            st += diz["w_wolf"][self.groupchats[chat_id].language]
                        if not self.groupchats[chat_id].game.stato_veggente:
                            st += diz["w_fortune"][self.groupchats[chat_id].language]
                        if not self.groupchats[chat_id].game.stato_protettore:
                            st += diz["w_protector"][self.groupchats[chat_id].language]
                        self.send_message(chat_id, st, message_id)

                    elif self.groupchats[chat_id].game.state == DAY:
                        st = diz["to_vote"][self.groupchats[chat_id].language]
                        st += "".join(["- " + p.name + "\n" for p in self.groupchats[chat_id].game.alivePlayers()
                                       if p.choice is None])
                        self.send_message(chat_id, st, message_id)

                    else:
                        st = engine.stateName(self.groupchats[chat_id].game.state, self.groupchats[chat_id].language) \
                             + "\n" + diz["alive"][self.groupchats[chat_id].language]
                        for p in self.groupchats[chat_id].game.alivePlayers():
                            st += p.name + "\n"
                        self.send_message(chat_id, st, message_id)
                else:
                    self.send_message(chat_id, diz["no_game"][self.groupchats[chat_id].language], message_id)
            else:
                self.send_message(chat_id, diz["info"][self.groupchats[chat_id].language], message_id)

        elif comw[0] == "help":
            st = diz["to_start"][self.groupchats[chat_id].language]
            self.send_message(chat_id, st, message_id)

        elif comw[0] == "rules":
            self.send_message(chat_id, diz['rules'][self.groupchats[chat_id].language])

        elif comw[0] == "language":
            if isgroup:
                if len(comw) < 2:
                    self.send_message(chat_id, diz['language_one'][self.groupchats[chat_id].language])
                else:
                    language = comw[1].lower().strip()
                    if language in ["en", "it"]:
                        self.groupchats[chat_id].language = language
                        self.send_message(chat_id, diz['language'][self.groupchats[chat_id].language])
                    else:
                        self.send_message(chat_id, diz['language_allowed'][self.groupchats[chat_id].language])
            else:
                self.send_message(chat_id, diz['language_group'][self.groupchats[chat_id].language], message_id)

        elif comw[0].isdigit():
            n = int(comw[0]) - 1

            if not isgroup:
                pl = None
                gpcp = None
                for gpc in self.groupchats:  # controllo se è notte e il messaggio viene da uno dei giocatori in gioco
                    if self.groupchats[gpc].game and self.groupchats[gpc].game.state == NIGHT:
                        pl = self.get_player(chat_id, gpc)
                        gpcp = gpc

                if pl is not None:
                    if pl.role == engine.lupo:
                        try:
                            if self.groupchats[gpcp].game.players[n].alive and \
                                    not self.groupchats[gpcp].game.stato_lupi:
                                pl.choice = n
                                self.groupchats[gpcp].game.stato_lupi = True
                                self.send_message(chat_id, diz["select"][self.groupchats[gpcp].language], message_id)
                            else:
                                self.send_message(chat_id, diz["no_alive"][self.groupchats[gpcp].language], message_id)
                        except (IndexError, KeyError):
                            self.send_message(chat_id, diz["no_exist"][self.groupchats[gpcp].language], message_id)

                    if pl.role == engine.veggente and not self.groupchats[gpcp].game.stato_veggente:
                        try:
                            if self.groupchats[gpcp].game.players[n].alive:
                                pl.choice = n
                                self.groupchats[gpcp].game.stato_veggente = True
                                self.send_message(chat_id, diz["select"][self.groupchats[gpcp].language], message_id)
                            else:
                                self.send_message(chat_id, diz["no_alive"][self.groupchats[gpcp].language], message_id)
                        except (IndexError, KeyError):
                            self.send_message(chat_id, diz["no_exist"][self.groupchats[gpcp].language], message_id)

                    if pl.role == engine.protettore and not self.groupchats[gpcp].game.stato_protettore:
                        try:
                            if self.groupchats[gpcp].game.players[n].alive:
                                pl.choice = n
                                self.groupchats[gpcp].game.stato_protettore = True
                                self.send_message(chat_id, diz["select"][self.groupchats[gpcp].language], message_id)
                            else:
                                self.send_message(chat_id, diz["no_alive"][self.groupchats[gpcp].language], message_id)
                        except (IndexError, KeyError):
                            self.send_message(chat_id, diz["no_exist"][self.groupchats[gpcp].language], message_id)

            else:
                if self.groupchats[chat_id].game and self.groupchats[chat_id].game.state == DAY:
                    p = self.get_player(m['from']['id'], chat_id)

                    if p is not None:
                        try:
                            if self.groupchats[chat_id].game.players[n].alive:
                                p.choice = n
                                self.repeat_votes(chat_id)
                            else:
                                self.send_message(chat_id, diz["no_alive"][self.groupchats[chat_id].language], message_id)
                        except (IndexError, KeyError):
                            self.send_message(chat_id, diz["no_exist"][self.groupchats[chat_id].language], message_id)
                    else:
                        self.send_message(chat_id, diz["no_part"][self.groupchats[chat_id].language],
                                          message_id)

    def get_player(self, player_id, game_id):
        """Get player, given player chat_id and group chat_id"""
        for p in self.groupchats[game_id].game.players:
            if p.chat_id == player_id:
                return p
        else:
            return None

    def repeat_votes(self, gpc):
        """Send votes summary"""
        st = ""

        votes = [0 for p in self.groupchats[gpc].game.players]
        for p in self.groupchats[gpc].game.players:
            if hasattr(p, "choice") and (p.choice is not None):
                votes[p.choice] += 1

        st += "".join([str("/") + str(p.index + 1) + " " + p.name + " " + "👎" * votes[p.index] + "\n"
                       for i, p in enumerate(self.groupchats[gpc].game.alivePlayers())])
        self.send_message(gpc, st)

        if sum(votes) >= len(self.groupchats[gpc].game.alivePlayers()):
            self.groupchats[gpc].game.state = DAY_END

    def night_message(self, gpc):
        """Night message in the group chat;
        private message for wolves, protectors and watchers."""

        self.send_message(gpc, diz["night"][self.groupchats[gpc].language])

        alive_p = ""
        ap = self.groupchats[gpc].game.alivePlayers()
        alive_p += "".join(["/" + str(p.index + 1) + " " + p.name + "\n" for p in ap])

        time.sleep(3)
        for players in self.groupchats[gpc].game.wolves():
            if len(self.groupchats[gpc].game.wolves()) > 1:
                st = diz["wolves"][self.groupchats[gpc].language]
                st += "".join(["-" + p.name + "\n" for p in self.groupchats[gpc].game.wolves()])
                st += diz["to_eat"][self.groupchats[gpc].language]
                self.send_message(players.chat_id, st)
            else:
                st = diz["to_eat_one"][self.groupchats[gpc].language]
                self.send_message(players.chat_id, st)

            self.send_message(players.chat_id, alive_p)

        for players in self.groupchats[gpc].game.watcher():
            self.send_message(players.chat_id, diz["to_watch"][self.groupchats[gpc].language])

            self.send_message(players.chat_id, alive_p)

        for players in self.groupchats[gpc].game.protector():
            self.send_message(players.chat_id, diz["to_protect"][self.groupchats[gpc].language])

            self.send_message(players.chat_id, alive_p)

        for i, p in enumerate(self.groupchats[gpc].game.players):
            self.groupchats[gpc].game.players[i].choice = None

    def do_step(self, gpc):
        """Do game step"""
        ggame = self.groupchats[gpc].game

        if ggame.state == RUOLI_ASSEGNATI:
            ggame.state = NIGHT
            self.send_message(gpc, diz["game_started"][self.groupchats[gpc].language])

            self.night_message(gpc)
            return

        if ggame.state == NIGHT_END:
            results = {}

            wolchoice = [p.choice for p in self.groupchats[gpc].game.wolves() if p.choice is not None]
            results['tomurder'] = wolchoice

            if len(ggame.watcher()) > 0:
                results['toview'] = self.groupchats[gpc].game.watcher()[0].choice

            if len(ggame.protector()) > 0:
                results['toprotect'] = self.groupchats[gpc].game.protector()[0].choice

            ret = ggame.inputNight(results)

            if len(ret['killed_now']) == 0:
                if ggame.figlio_del_lupo:
                    self.send_message(gpc, diz["new_wolf"][self.groupchats[gpc].language])
                    ggame.figlio_del_lupo = False
                else:
                    self.send_message(gpc, diz["no_kill"][self.groupchats[gpc].language])
            elif len(ret['killed_now']) == 1:
                self.send_message(gpc, ggame.players[ret['killed_now'][0]].name +
                                  diz["is_died"][self.groupchats[gpc].language])

            for k in ret['killed_now']:
                self.send_message(ggame.players[k].chat_id, diz["you_died"][self.groupchats[gpc].language])

            if "toview" in results:
                try:
                    self.send_message(ggame.watcher()[0].chat_id, diz["he_is"][self.groupchats[gpc].language] +
                                      {True: diz["good"][self.groupchats[gpc].language],
                                       False: diz["bad"][self.groupchats[gpc].language]
                                       }[ggame.players[results['toview']].role.good])
                except IndexError:
                    pass

            time.sleep(3)

            self.send_message(gpc, diz["day"][self.groupchats[gpc].language])

            if ggame.state != FINISH:  # solo se la partita non è finita
                time.sleep(3)

                f = diz["vote"][self.groupchats[gpc].language]

                ap = ggame.alivePlayers()
                f += "".join(["/" + str(p.index + 1) + " " + p.name + "\n" for p in ap])

                self.send_message(gpc, f)

                for p in self.groupchats[gpc].game.players:
                    p.choice = None

            return

        if ggame.state == DAY_END:
            votes = [0 for p in self.groupchats[gpc].game.players]
            for p in self.groupchats[gpc].game.players:
                if hasattr(p, "choice") and (p.choice is not None):
                    votes[p.choice] += 1

            vmax = max(votes)

            besters = [i for i, v in enumerate(votes) if v == vmax]

            di = None
            if len(besters) == 0:
                self.logger.error("ERROR")
            elif len(besters) == 1:
                self.send_message(gpc, ggame.players[besters[0]].name + diz["hanged"][self.groupchats[gpc].language])
                di = besters[0]
            else:
                st = diz["tied"][self.groupchats[gpc].language]
                for i in besters:
                    st += ggame.players[i].name + "\n"
                di = random.choice(besters)
                st += diz["chance"][self.groupchats[gpc].language] % ggame.players[di].name
                self.send_message(gpc, st)

            ggame.inputDay(di, len(self.groupchats[gpc].game.watcher()), len(self.groupchats[gpc].game.protector()))

            if ggame.state != FINISH:
                self.send_message(ggame.players[di].chat_id, diz["you_hanged"][self.groupchats[gpc].language])
                self.night_message(gpc)
            return

    def cycle(self, gpc=None):

        time.sleep(2 / (len(self.groupchats) + 1))
        self.get_messages()

        for gpc in self.groupchats:  # game started
            if self.groupchats[gpc].game and self.groupchats[gpc].game.state == NIGHT and \
                    not self.groupchats[gpc].game.stato_veggente:
                self.groupchats[gpc].game.stato_veggente = False if len(self.groupchats[gpc].game.watcher()) >= 1 \
                    else True
            if self.groupchats[gpc].game and self.groupchats[gpc].game.state == NIGHT and \
                    not self.groupchats[gpc].game.stato_protettore:
                self.groupchats[gpc].game.stato_protettore = False if len(self.groupchats[gpc].game.protector()) >= 1 \
                    else True

            if self.groupchats[gpc].game and self.groupchats[gpc].game.state == NIGHT and \
                    self.groupchats[gpc].game.stato_veggente and self.groupchats[gpc].game.stato_protettore and \
                    self.groupchats[gpc].game.stato_lupi:
                self.groupchats[gpc].game.stato_lupi = False
                self.groupchats[gpc].game.state = NIGHT_END

            if self.groupchats[gpc].game and self.groupchats[gpc].game.state in [DAY_END, RUOLI_ASSEGNATI, NIGHT_END]:
                self.do_step(gpc)

            if self.groupchats[gpc].game and self.groupchats[gpc].game.state == FINISH:
                self.send_message(gpc, diz["results"][self.groupchats[gpc].language] + engine.sideName(
                    self.groupchats[gpc].game.win, self.groupchats[gpc].language))
                self.stop_game(gpc)

        while self.updates:
            self.logger.info("processing update...")
            u = self.updates.pop(0)
            self.process_update(u, gpc)

        try:
            self.logger.debug("Attivo in %d chat." % len(self.groupchats))
        except KeyError:
            self.logger.error("KEYERROR")


if __name__ == "__main__":
    bot = LupusBot()
    while True:
        bot.cycle()

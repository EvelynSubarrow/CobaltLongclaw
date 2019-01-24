#!/usr/bin/env python3

import argparse, random, select, string, subprocess, time, threading, sys
import socket, resource
import logging

import sockschain as socks, stem, stem.control

from IPython.terminal.embed import InteractiveShellEmbed
import IPython
from traitlets import config


from Bot import Bot
import EventManager, IRCLineHandler

IRC_COLORS = ["02", "03", "04", "05", "06", "07", "08", "09",
    "10", "11", "12", "13"]

def read_proxy_list(filename):
    with open(filename) as f:
        plist = [line.split() for line in f.read().split("\n")]
        proxies = set()
        for line in plist:
            if not line: continue
            # 4 1.1.1.1:1234 RU -
            if ":" in line[1]:
                hostport = line[1].split(":")
                proxies.add((line[0], hostport[0], int(hostport[1])))
            # 4 1234 1.1.1.1 RU -
            else:
                proxies.add((line[0], line[2], int(line[1])))
    return proxies

LOG_LEVELS = {
    "trace": logging.DEBUG-1,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARN,
    "error": logging.ERROR,
    "critical": logging.CRITICAL
}

loggers = {}

def get_logger(name):
    global loggers
    if name in loggers:
        return loggers[name]

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    # This mode ensures that logs will be overwritten on each run
    handler = logging.FileHandler("logs/{}.log".format(name), mode="w")
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    loggers[name] = logger
    return logger

def log_message(name, message, level="info"):
    get_logger(name).log(LOG_LEVELS[level], message)

def new_circuit(tor_password, tor_port):
    log_message("proxy", "Acquiring new Tor circuit")
    with stem.control.Controller.from_port(port = tor_port
            ) as controller:
        controller.authenticate(tor_password)
        controller.signal(stem.Signal.NEWNYM)

def new_socket(proxies):
    s = socks.socksocket()
    for protocol, host, port in proxies:
        s.addproxy({"5": socks.PROXY_TYPE_SOCKS5, "4": socks.PROXY_TYPE_SOCKS4, "H": socks.PROXY_TYPE_HTTP}[protocol], host, port)
    s.settimeout(2.5)
    log_message("proxy", " -> ".join(["{} {}:{}".format(protocol, host, port) for protocol,host,port in proxies]))
    return s

# List of characters, minimum bound, maximum bound (inclusive)
def random_string(letterset, min, max):
    return "".join(random.choice(letterset) for a in range(min,max+1))

def rainbow_string(s):
    rainbow = ""
    for c in s:
        color = random.choice(IRC_COLORS)
        rainbow += "\x03%s,00%s" % (color, c)
    return rainbow

class IdentityProvider:
    # Tuple of nickname, username (or ident, if you prefer), and "real name"
    def new_identity(self):
        return ("CobaltLongclaw", "CobaltLongclaw", "CobaltLongclaw r2")

class RandomIdentityProvider(IdentityProvider):
    def new_identity(self):
        return (random_string(string.ascii_lowercase,2,11), random_string(string.ascii_lowercase,2,11),
            random_string(string.ascii_lowercase,2,11))

class AnimalIdentityProvider(IdentityProvider):
    former = ["Black", "White", "Grey", "Crimson", "Azure", "Aqua", "Violet", "Ash", "Blood", "Argent", "Copper", "Zinc", "Iron", "Gold", "Silver", "Chrome", "Cobalt"]
    latter = ["Wolf", "Eagle", "Fox", "Bear", "Scorpion", "Deer", "Swallow", "Goat", "Dragon"]
    def new_identity(self):
        name = random.choice(former) + random.choice(latter)
        return (name, name, name)

class LambdaIdentityProvider(IdentityProvider):
    def __init__(identity_function):
        self.new_identity = identity_function

class BotManager(object):
    def __init__(self):
        self.bots = {}
        self.running = True
        self.events = EventManager.EventHook(self)

        def set_status(event):
            event["bot"].last_status = event["command"]
        self.events.single("received/numeric").hook(set_status)

        self.poll = select.epoll()
        self._random_nicknames = []

    def run(self):
        while self.running:
            events = self.poll.poll(10)
            for fileno, event in events:
                bot = self.bots[fileno]
                if event & select.EPOLLIN:
                    lines = bot.read()
                    if not lines:
                        self.remove_bot(bot)
                    else:
                        for line in lines:
                            self.parse_line(line, bot)
                elif event & select.EPOLLOUT:
                    bot.send()
                    self.poll.modify(bot.fileno(),
                        select.EPOLLIN)
                elif event & select.EPOLLHUP:
                    self.remove_bot(bot)

            for bot in list(self.bots.values()):
                since_last_read = (
                    None if not bot.last_read else time.time(
                    )-bot.last_read)
                removed = False
                if since_last_read:
                    if since_last_read > 120:
                        self.remove_bot(bot)
                        removed = True
                    elif since_last_read > 30 and not bot.ping_sent:
                        bot.send_ping()
                if not removed and bot.waiting_send():
                    self.poll.modify(bot.fileno(),
                        select.EPOLLIN|select.EPOLLOUT)

    def parse_line(self, line, bot):
        if not line:
            return
        original_line = line
        prefix, final = None, None
        if line[0] == ":":
            prefix, line = line[1:].split(" ", 1)
        command, line = (line.split(" ", 1) + [""])[:2]
        if line[0] == ":":
            final, line = line[1:], ""
        elif " :" in line:
            line, final = line.split(" :", 1)
        args_split = line.split(" ") if line else []
        if final:
            args_split.append(final)
        IRCLineHandler.handle(original_line, prefix, command, args_split, final!=None, bot, self)

    def all(self, function, *args):
        for bot in list(self.bots.values()):
            function(bot, *args)

    def add_bot(self, bot):
        self.bots[bot.fileno()] = bot
        self.poll.register(bot.fileno(), select.EPOLLIN)

    def remove_bot(self, bot):
        self.poll.unregister(bot.fileno())
        del self.bots[bot.fileno()]

    def __len__(self):
        return len(self.bots)

    def start(self):
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()
        return self.thread

    def summary(self):
        return ", ".join([a.summary() for a in self.bots.values()])

class ClientFactory(object):
    def __init__(self, host, port, bot_count, tor_password,
            tor_port, proxies, use_tor=True, circuit_cycle=1, min_chain_len=1):
        self.bot_manager = BotManager()
        self.host = host
        self.port = port
        self.bot_count = bot_count
        self.tor_password = tor_password
        self.tor_port = tor_port
        self.running = True
        self.thread = threading.Thread()
        self.connection_count = 0
        self.use_tor = use_tor
        self.proxies = proxies
        self.circuit_cycle = circuit_cycle
        self.identity_provider = RandomIdentityProvider()
        self.minimum_chain_length = min_chain_len

    def run(self):
        log_message("proxy", "ClientFactory thread started")

        while self.running:
            if len(self.bot_manager.bots) < self.bot_count:
                count = min(self.bot_count-len(self.bot_manager.bots),
                    self.circuit_cycle)
                if self.use_tor:
                    new_circuit(self.tor_password, self.tor_port)
                sockets = []
                for n in range(count):
                    chain_list = []
                    if self.use_tor:
                        chain_list.append(("5", "localhost", 9050))
                    if self.proxies:
                        chain_list.append(proxies.pop())
                    if len(chain_list)>=self.minimum_chain_length:
                        sockets.append((new_socket(chain_list), chain_list[-1][0]))
                    else:
                        log_message("proxy", "All proxy chain options exhausted", "error")
                for socket, proxy_alias in sockets:
                    try:
                        socket.connect((self.host, self.port))
                    except (socks.Socks4Error, socks.Socks5Error, socks.Socks5AuthError) as e:
                        log_message("proxy", type(e).__name__ + " " + e.args[0][1], "error")
                        continue
                    except Exception as e:
                        log_message("proxy", "Other socket issue", "error")
                        continue
                    bot = Bot(socket, *self.identity_provider.new_identity())
                    bot.identify()
                    self.connection_count += 1
                    self.bot_manager.add_bot(bot)
                time.sleep(5)
            else:
                time.sleep(1)

    def start(self):
        self.bot_manager.start()
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()
        return self.thread

    def __repr__(self):
        return "<{0}({1} {2}/{3} ({5}))> - [{4}]".format(self.__class__.__name__, "running"*self.thread.is_alive() or "stopped",
            len(self.bot_manager), self.bot_count, self.bot_manager.summary(), self.connection_count)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="host of the irc server")
    parser.add_argument("port", type=int, help="port of the irc server")
    parser.add_argument("-n", "--bot-count", type=int, default=100, help=
        "amount of bots to create")
    parser.add_argument("-tp", "--tor-password", help=
        "password to use to authenticate with Tor control")
    parser.add_argument("-tr", "--tor-port", type=int, help=
        "Tor's control port", default=9051)
    parser.add_argument("-t", "--use-tor", action="store_true", default=True)
    parser.add_argument("-p", "--proxy-list", help="List of SOCKS/HTTP proxies to use")
    parser.add_argument("-m", "--minimum-chain-length", help="Treat proxies as exhausted below this count", default=1, type=int)
    parser.add_argument("-tc", "--tor-circuit-cycle", type=int,
        help="Cycle Tor exit after n connections", default=1)

    args = parser.parse_args()

    resource.setrlimit(resource.RLIMIT_NOFILE, (2000, 3000))

    proxies = []
    if args.proxy_list:
        proxies = read_proxy_list(args.proxy_list)

    client_factory = ClientFactory(args.host, args.port,
        args.bot_count, args.tor_password, args.tor_port, proxies, args.use_tor, args.tor_circuit_cycle, args.minimum_chain_length)

    bot_manager = client_factory.bot_manager

    sys.argv = sys.argv[:1]
    c = config.Config()
    c.InteractiveShell.banner1 = "`client_factory`, `bot_manager`"
    ip = InteractiveShellEmbed(config=c, user_ns=locals())
    IPython.get_ipython = lambda: ip
    ip()

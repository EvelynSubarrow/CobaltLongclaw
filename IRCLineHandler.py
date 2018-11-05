import re, threading

import Utils

RE_PREFIXES = re.compile(r"\bPREFIX=\((\w+)\)(\W+)(?:\b|$)")
RE_CHANMODES = re.compile(
    r"\bCHANMODES=(\w*),(\w*),(\w*),(\w*)(?:\b|$)")
RE_CHANTYPES = re.compile(r"\bCHANTYPES=(\W+)(?:\b|$)")

handlers = {}
descriptions = {}
default_events = {}
current_description = None
current_default_event = False

class LineData:
    def __init__(self, line, line_split, prefix, command, args, is_final, bot, server):
        self.line, self.prefix = line, prefix
        self.command, self.args = command, args
        self.is_final = is_final,
        self.server, self.line_split = server, line_split
        self.bot = bot
        self.prefix_split = Utils.separate_hostmask(self.prefix) if self.prefix else (None, None, None)

    def map(self):
        return {
            "line": self.line, "line_split": self.line_split,
            "prefix": self.prefix, "command": self.command,
            "args":  self.args, "is_final": self.is_final,
            "bot": self.bot, "prefix_split": self.prefix_split,
            }

def handler(f=None, description=None, default_event=False):
    global current_description, current_default_event
    if not f:
        current_description = description
        current_default_event = default_event
        return handler
    name = f.__name__.split("handle_")[1].upper()
    handlers[name] = f

    descriptions[name] = current_description
    default_events[name] = current_default_event
    current_description, current_default_event = None, False

def handle(line, prefix, command, args, is_final, bot, server):
    line_split = line.split(" ")
    data = LineData(line, line_split, prefix, command, args, is_final, bot, server)
    handler_function = None

    if command in handlers:
        handler_function = handlers[command]
    if default_events.get(command, False) or not command in handlers:
        if command.isdigit():
            server.events.on("received").on("numeric").call(
                number=command, **data.map())
            server.events.on("received").on("numeric").on(
                command).call(number=command, **data.map())
        else:
            server.events.on("received").on(command).call(**data.map())
    if handler_function:
        handler_function(data)

@handler(description="reply to a ping")
def handle_PING(data):
    nonce = data.args[0]
    data.bot.send_pong(nonce)
    data.server.events.on("received").on("ping").call(nonce=nonce, **data.map())

@handler(description="the first line sent to a registered client", default_event=True)
def handle_001(data):
    data.bot.nickname = data.args[0]

@handler(description="on user joining channel")
def handle_JOIN(data):
    server, bot = data.server, data.bot
    nickname, username, hostname = Utils.separate_hostmask(data.prefix)
    channel = Utils.remove_colon(data.args[0])
    if not bot.is_own_nickname(nickname):
        server.events.on("received").on("join").call(channel=channel,
            user=nickname, **data.map())
    else:
        bot.add_channel(channel)
        server.events.on("self").on("join").call(channel=channel, **data.map())
        bot.send_who(channel)

@handler(description="on user parting channel")
def handle_PART(data):
    server = data.server
    nickname, username, hostname = Utils.separate_hostmask(data.prefix)
    channel = data.args[0]
    reason = data.args[1] if len(data.args) > 1 else ""
    if not data.bot.is_own_nickname(nickname):
        server.events.on("received").on("part").call(channel=channel,
            reason=reason, user=nickname, **data.map())
    else:
        data.bot.remove_channel(channel)
        server.events.on("self").on("part").call(channel=channel,
            reason=reason, **data.map())

@handler(description="oh noes")
def handle_KICK(data):
    server, bot = data.server, data.bot
    nickname, username, hostname = Utils.separate_hostmask(data.prefix)
    channel = data.args[0]
    target_nick = data.args[1]
    reason = data.args[2] if len(data.args) > 2 else ""
    if data.bot.is_own_nickname(target_nick):
        data.bot.remove_channel(channel)
        server.events.on("self").on("kick").call(channel=channel,
            reason=reason, **data.map())
    else:
        server.events.on("received").on("kick").call(channel=channel,
            reason=reason, user=target_nick, **data.map())

@handler(description="The server is telling us about its capabilities!")
def handle_CAP(data):
    capability_list = []
    if len(data.args) > 2:
        capability_list = data.args[2].split()
    data.server.events.on("received").on("cap").call(subcommand=data.args[1],
        capabilities=capability_list, **data.map())

@handler(description="The server is asking for authentication")
def handle_AUTHENTICATE(data):
    data.server.events.on("received").on("authenticate").call(message=data.args[0],
        **data.map())

@handler(description="someone has changed their nickname")
def handle_NICK(data):
    new_nickname = data.args[0]
    old_nickname = data.prefix_split[0]
    if old_nickname != data.bot.nickname:
        data.server.events.on("received").on("nick").call(new_nickname=new_nickname,
            old_nickname=old_nickname, **data.map())
    else:
        data.bot.nickname = new_nickname
        data.server.events.on("self").on("nick").call(new_nickname=new_nickname,
            old_nickname=old_nickname, **data.map())

@handler(description="I've been invited somewhere")
def handle_INVITE(data):
    nickname, username, hostname = Utils.separate_hostmask(data.prefix)
    target_channel = Utils.remove_colon(data.args[1])
    data.server.events.on("received").on("invite").call(
        user=nickname, target_channel=target_channel, **data.map())

@handler(description="we've received a message")
def handle_PRIVMSG(data):
    server = data.server
    nickname, username, hostname = Utils.separate_hostmask(data.prefix)
    user = nickname
    message = "" if len(data.args) < 2 else data.args[1]
    message_split = message.split(" ")
    target = data.args[0]
    action = message.startswith("\01ACTION ") and message.endswith("\01")
    if action:
        message = message.replace("\01ACTION ", "", 1)[:-1]
    if target[0] in ["#", "&"]:
        channel = data.args[0]
        server.events.on("received").on("message").on("channel").call(
            user=user, message=message, message_split=message_split,
            channel=channel, action=action, **data.map())
    elif target==data.bot.nickname:
        server.events.on("received").on("message").on("private").call(
            user=user, message=message, message_split=message_split,
            action=action, **data.map())

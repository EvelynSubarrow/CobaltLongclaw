# CobaltLongclaw
A event-driven python3 IRC bot, capable of maintaining hundreds of simultaneous connections through Tor or a list of proxies (
SOCKS 4/5, HTTP connect, and open linux shells with telnet are supported),
with an interactive IPython shell for manipulation.

CobaltLongclaw's event system is derived from that of [Bitbot](https://github.com/jesopo/bitbot), although the separator is a '/',
and parameters passed aren't processed beyond simple parsing.

## Dependencies
* [stem](https://pypi.org/project/stem/)
* [IPython](https://pypi.org/project/ipython/)

Use `pip3 install -r requirements.txt` to install them all at once.

## Licensing
CobaltLongclaw is licenced under the [Creative Commons BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) licence,
with the exception of the sockschain module, which contains details of its licence.

## Using CobaltLongclaw
```
./shell.py -n 10 irc.example.com 6667
In [1]: bot_manager.events.single("received/numeric/001").hook(lambda event: event["bot"].send_join("#Botchannel"))
In [2]: client_factory.start()
```

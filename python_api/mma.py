#!/usr/bin/python3

import argparse, configparser, json, logging, os, pwd, re, shlex, sys
from requests.auth import HTTPDigestAuth
from marklogic import MarkLogic
import marklogic.cli.manager
from marklogic.connection import Connection
from marklogic.cli.template import Template

class MMA():
  def __init__(self):
    try:
      inifile = "{0}/.marklogic.ini".format(os.environ['HOME'])
    except KeyError:
      print("Configuration problem, no HOME in environment?")
      sys.exit(1)

    self.config = configparser.ConfigParser()
    self.config.read(inifile)
    self. cli = Template()

  def main(self):
    self.argv = sys.argv
    self.script = self.argv[0]
    del(self.argv[0]) # trim off the script name

    if len(self.argv) == 0 or self.argv[0] == '-h' or self.argv[0] == '--help':
      self.usage()
    else:
      self.run(self.argv)

  def run(self, argv):
    command = None
    artifact = None

    # This is an odd program. The parser used for each line depends on
    # the command and the different parsers can be cranky about the
    # allowed order of commands, options, and parameters. So we start
    # by trying to "normalize" it all.
    options = []
    params = []
    positional = []
    optarg = False
    for tok in argv:
      if optarg:
        options.append(tok)
        optarg = False
      elif tok.startswith("-"):
        options.append(tok)
        if tok != "--debug":
          optarg = True
      elif "=" in tok:
        params.append(tok)
      else:
        positional.append(tok)

    try:
      command = positional[0]
    except IndexError:
      print("Usage: {0} command artifact ...".format(self.script))
      sys.exit(1)

    empty_artifact_commands = {'start','status', 'stop', 'init',
                               'save', 'switch', 'clear', 'log'}
    try:
      artifact = positional[1]
    except IndexError:
      if command in empty_artifact_commands:
        pass
      else:
        print("Usage: {0} command artifact ...".format(self.script))
        sys.exit(1)

    # Hack for the server case
    if artifact in ['http','xdbc','odbc','webdav']:
      stype = artifact
      if command == 'list':
        artifact = 'servers'
      else:
        artifact = 'server'
      positional[1] = artifact
      if positional[2] == artifact:
        del(positional[2])
      options.append("--type")
      options.append(stype)

    # Hack for the stop case
    if command == 'stop' and artifact is None:
      positional.append('host')
      artifact = 'host'

    argv = []
    argv.extend(options)
    argv.extend(positional)
    argv.extend(params)

    templ = self.cli.command_template(command)
    if templ is None:
      print("The command '{0}' is unrecognized".format(command))
      sys.exit(1)

    if artifact is None:
      if 'parser' in templ:
        parser = templ['parser']
      else:
        print("The command '{0}' isn't recognized."
              .format(command,artifact))
        sys.exit(1)
    else:
      if artifact in templ:
        parser = templ[artifact]["parser"]
      else:
        print("The command '{0}' doesn't take '{1}' artifacts."
              .format(command,artifact))
        sys.exit(1)

    args = vars(parser.parse_args(argv))

    if args['debug']:
      logging.basicConfig(level=logging.WARNING)
      logging.getLogger("requests").setLevel(logging.WARNING)
      logging.getLogger("marklogic").setLevel(logging.DEBUG)
    else:
      logging.basicConfig(level=logging.INFO)
      logging.getLogger("requests").setLevel(logging.WARNING)
      logging.getLogger("marklogic").setLevel(logging.INFO)

    try:
      username, password = re.split(":", args['credentials'])
    except ValueError:
      print ("--credentials value must be 'user:password':",
             args['credentials'])
      sys.exit(1)

    host = args['hostname']
    conn = Connection(host, HTTPDigestAuth(username, password))

    # do it!
    if command == 'run':
      self.process_script(args['script'])
    else:
      if artifact is None:
        templ["code"](args, self.config, conn)
      else:
        templ[artifact]["code"](args, self.config, conn)

  def process_script(self, scriptfn):
    print("Running", scriptfn)
    script = open(scriptfn, 'r')
    command = ""
    for line in script:
      line = line.strip()
      command = command + line
      if command.endswith("\\"):
        command = command[:-1]
      else:
        command = command.strip()
        #print(shlex.split(command))
        self.run(shlex.split(command))
        command = ""

    if command != "":
      print("Error: premature end of file on {0}".format(scriptfn))
      sys.exit(1)

  def usage(self):
    print("MarkLogic Management API")
    print("Command line:")
    print("  command [artifact] {0}, {1}"
          .format("[--opt1 [--opt2 ...]]",
                  "[prop1=value [prop2=value...]]"))
    print("Where: command [artifact] is:")

    parsers = self.cli.parsers()
    for cmd in parsers:
      if 'code' in parsers[cmd]:
        p = parsers[cmd]['parser']
        print("  %-15s  %s" % (cmd, p.description))

    for cmd in parsers:
      if 'code' not in parsers[cmd]:
        for art in parsers[cmd]:
          try:
            if 'code' in parsers[cmd][art]:
              p = parsers[cmd][art]['parser']
              print("  %-15s  %s" % (cmd + " " + art, p.description))
          except TypeError:
            pass
    print("")
    print("For more detail, try 'command [artifact] --help'")

if __name__ == '__main__':
  mma = MMA()
  mma.main()

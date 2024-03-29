#!/usr/bin/python2

# {{{ Imports
import socket
import json
import os
import random
import sys
from socket import error as SocketError
import errno
sys.path.append("../..")
import src.game.game_constants as game_consts
from src.game.character import *
from src.game.gamemap import *
# }}}

gameMap = GameMap()

teamName = "DefaultArcher"

destinations = {}

# {{{ Team Composition Setup
def initialResponse():
    return {
        'TeamName': "DefaultArcher",
        'Characters': [ {
                "CharacterName": "Legolas",
                "ClassId": "Archer"
            }, {
                "CharacterName": "Ashe",
                "ClassId": "Archer"
            }, {
                "CharacterName": "Varus",
                "ClassId": "Archer"
            }
    ] }
# }}}

# {{{ Helper Functions

def getQuadrant(hero):
    x = hero.position[0]
    y = hero.position[1]
    if 0 <= x and x <= 2 and 0 <= y and y <= 2:
        return 2
    elif 0 <= x and x <= 2 and 2 <= y and y <= 4:
        return 1
    elif 2 <= x and x <= 4 and 0 <= y and y <= 2:
        return 3
    elif 2 <= x and x <= 4 and 2 <= y and y <= 4:
        return 4
    else:
        return "wtf lulz where the fuck are you"

def manhattanDist(hero1, hero2): # Cuz DotA > League
    pos1 = hero1.position
    pos2 = hero2.position
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

def getSprintDestination(hero):
    quadrant = getQuadrant(hero)
    if quadrant == 1:
        return (4, 0)
    elif quadrant == 2:
        return (4, 4)
    elif quadrant == 3:
        return (0, 4)
    elif quadrant  == 4:
        return (0, 0)

def getKiteLoc(hero, villain):
    myPos = hero.position
    vilPos = villain.position
    newX = min(myPos[0] + (myPos[0] - vilPos[0]), 4)
    newY = min(myPos[1] + (myPos[1] - vilPos[1]), 4)
    # We have edge cases
    if myPos == (0, 0):
        if vilPos[0] == 0:
            newX = 1
            newY = 0
        elif vilPos[1] == 0:
            newY = 1
            newX = 0
    elif myPos == (0, 4):
        if vilPos[0] == 0:
            newX = 1
            newY = 4
        elif vilPos[1] == 4:
            newY = 3
            newX = 0
    elif myPos == (4, 4):
        if vilPos[0] == 4:
            newX = 3
            newY = 4
        elif vilPos[1] == 4:
            newY = 3
            newX = 4
    elif myPos == (4, 0):
        if vilPos[0] == 4:
            newX = 3
            newY = 0
        if vilPos[1] == 0:
            newY = 1
            newX = 4
    return (newX, newY)

def isStunned(hero):
    return hero.attributes.get_attribute("Stunned")

def isSilenced(hero):
    return hero.attributes.get_attribute("Silenced")

def isRooted(hero):
    return hero.attributes.get_attribute("Rooted")
# }}}

# Determine actions to take on a given turn, given the server response
def processTurn(serverResponse):
# {{{ Parse Server Response
    actions = []
    myteam = []
    enemyteam = []
    for team in serverResponse["Teams"]:
        if team["Id"] == serverResponse["PlayerInfo"]["TeamId"]:
            for characterJson in team["Characters"]:
                character = Character()
                character.serialize(characterJson)
                myteam.append(character)
        else:
            for characterJson in team["Characters"]:
                character = Character()
                character.serialize(characterJson)
                enemyteam.append(character)
# }}}
    # Choose a target
    target = None
    least_health = None
    opponent_CC = { "stun" : False, "silence" : False, "root" : False }
    for character in enemyteam:
        if character.is_dead():
            continue
        if least_health == None or character.attributes.health < least_health:
            least_health = character.attributes.health
            target = character
        # Determine what CC options the opponent has that can possibly hit you

    if target:
        for character in myteam:
            # if character.in_range_of(target, gameMap):
            # Turns out in_range_of is a broken implementation. If will only
            # return True if 2 entities are in within the SMALLER range between
            # the 2 entities, not the largest...
            dist = manhattanDist(character, target)
            # print dist
            if dist <= character.attributes.attackRange:
                if 0 <= dist and dist <= 1:
                    if character.abilities[12] == 0:
                        destinations[character.id] = getSprintDestination(character)
                        actions.append({
                            "Action" : "Cast",
                            "CharacterId" : character.id,
                            "TargetId" : character.id,
                            "AbilityId" : 12
                        })
                    else:
                        actions.append({
                            "Action" : "Move",
                            "Location" : destinations.get(character.id,
                                getSprintDestination(character)),
                            "CharacterId" : character.id
                        })
                elif 1 < dist and dist < character.attributes.attackRange:
                    # print "Moving"
                    # print getKiteLoc(character, target)
                    actions.append({
                        "Action" : "Move",
                        "Location" : getKiteLoc(character, target),
                        "CharacterId": character.id,
                    })
                else:
                    # print "ATTACKING!!!!!"
                    actions.append({
                        "Action": "Attack",
                        "CharacterId": character.id,
                        "TargetId": target.id
                    })
            else:
                actions.append({
                    "Action": "Attack",
                    "CharacterId": character.id,
                    "TargetId": target.id
                })

    return {
        'TeamName': teamName,
        'Actions': actions
    }

# {{{ Main method. Do NOT MODIFY!
if __name__ == "__main__":
    # Config
    conn = ('localhost', 1337)
    if len(sys.argv) > 2:
        conn = (sys.argv[1], int(sys.argv[2]))

    # Handshake
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(conn)

    # Initial connection
    s.sendall(json.dumps(initialResponse()) + '\n')

    # Initialize test client
    game_running = True
    members = None

    # Run game
    try:
        data = s.recv(1024)
        while len(data) > 0 and game_running:
            value = None
            if "\n" in data:
                data = data.split('\n')
                if len(data) > 1 and data[1] != "":
                    data = data[1]
                    data += s.recv(1024)
                else:
                    value = json.loads(data[0])

                    # Check game status
                    if 'winner' in value:
                        game_running = False

                    # Send next turn (if appropriate)
                    else:
                        msg = processTurn(value) if "PlayerInfo" in value else initialResponse()
                        s.sendall(json.dumps(msg) + '\n')
                        data = s.recv(1024)
            else:
                data += s.recv(1024)
    except SocketError as e:
        if e.errno != errno.ECONNRESET:
            raise  # Not error we are looking for
        pass  # Handle error here.
    s.close()
# }}}


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

teamName = "ArrayToTheKnee"

# {{{ Team Composition Setup
def initialResponse():
    return {
        'TeamName': "arraytotheknee",
        'Characters': [{
                "CharacterName": "Ashe",
                "ClassId": "Archer"
            }, {
                "CharacterName": "Varus",
                "ClassId": "Archer"
            }, {
                "CharacterName": "Druid",
                "ClassId": "Druid"
            }
    ] }
# }}}

# {{{ Helper Functions

def manhattanDist(hero1, hero2): # Cuz DotA > League
    pos1 = hero1.position
    pos2 = hero2.position
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

def getKiteLoc(hero, villain):
    myPos = hero.position
    vilPos = villain.position
    newX = min(myPos[0] + (myPos[0] - vilPos[0]), 4)
    newY = min(myPos[1] + (myPos[1] - vilPos[1]), 4)
    # We have edge cases
    if myPos == (0, 0):
        if vilPos[0] == 0:
            newX = 1
        elif vilPos[1] == 0:
            newY = 1
    elif myPos == (0, 4):
        if vilPos[0] == 0:
            newX = 1
        elif vilPos[1] == 4:
            newY = 3
    elif myPos == (4, 4):
        if vilPos[0] == 4:
            newX = 3
        elif vilPos[1] == 4:
            newY = 3
    elif myPos == (4, 0):
        if vilPos[0] == 4:
            newX = 3
        if vilPos[1] == 0:
            newY = 1
    return (newX, newY)

def isStunned(hero):
    return hero.attributes.get_attribute("Stunned")

def isSilenced(hero):
    return hero.attributes.get_attribute("Silenced")

def isRooted(hero):
    return hero.attributes.get_attribute("Rooted")

def isArcher(hero):
    return hero.classId == "Archer"
def allAtMaxHealth(team):
    for character in team:
        if(character.attributes.health < character.attributes.maxHealth):
            return False
    return True
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
    least_health_enemy = None
    least_health_ally = None
    opponent_CC = { "stun" : False, "silence" : False, "root" : False }
    for enemy in enemyteam:
        if enemy.is_dead():
            continue
        if least_health_enemy == None or enemy.attributes.health < least_health_enemy.attributes.health:
            least_health_enemy = enemy
            target = enemy
        # Determine what CC options the opponent has that can possibly hit you

    for ally in myteam:
        if ally.is_dead():
           continue
        if least_health_ally == None or ally.attributes.health < least_health_ally.attributes.health:
            least_health_ally = ally

    if target:
        for character in myteam:
            print character.attributes.health
            # if character.in_range_of(target, gameMap):
            # Turns out in_range_of is a broken implementation. If will only
            # return True if 2 entities are in within the SMALLER range between
            # the 2 entities, not the largest...
            dist = manhattanDist(character, target)
            #print dist
            if dist <= character.attributes.attackRange:
                if 0 < dist and dist <= target.attributes.attackRange:
                    actions.append({
                        "Action": "Move",
                        "Location": getKiteLoc(character, target)
                    })
            if(isArcher(character)):
                print "Archer Attack"
                actions.append({
                    "Action": "Attack",
                    "CharacterId": character.id,
                    "TargetId": target.id
                })
            else:
                #Druid Code
                didCast = False
                if not allAtMaxHealth(myteam):
                    for abilityId, cooldown in character.abilities.items():
                        print str(cooldown) + " " + str(abilityId)
                        # Do I have an ability not on cooldown
                        if character.casting == None:
                            if cooldown == 0 and int(abilityId) == 3:
                                # If I can, then cast it
                                ability = game_consts.abilitiesList[int(abilityId)]
                                # Get ability
                                print "Druid Heal"
                                actions.append({
                                    "Action": "Cast",
                                    "CharacterId": character.id,
                                    # Am I buffing or debuffing? If buffing, target myself
                                    "TargetId": least_health_ally.id,
                                    "AbilityId": int(abilityId)
                                })
                                didCast = True
                        else:
                            didCast = True
                    # Was I able to cast something? Either wise attack
                if not didCast:
                    print "Druid Attack"
                    actions.append({
                        "Action": "Attack",
                        "CharacterId": character.id,
                        "TargetId": target.id,
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


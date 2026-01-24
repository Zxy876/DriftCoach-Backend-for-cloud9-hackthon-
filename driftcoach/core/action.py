from enum import Enum


class Action(str, Enum):
    SAVE = "SAVE"
    RETAKE = "RETAKE"
    FORCE = "FORCE"
    ECO = "ECO"
    CONTEST = "CONTEST"
    TRADE = "TRADE"

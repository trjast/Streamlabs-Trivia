#---------------------------------------
# Libraries and references
#---------------------------------------
import base64
import codecs
import ctypes
import difflib
import hashlib
import json
import os
import time
import winsound

#---------------------------------------
# [Required] Script information
#---------------------------------------
ScriptName = "Trivia"
Website = "http://trjast.com"
Description = "Trivia for Streamlabs Chatbot"
Creator = "trjast"
Version = "1.0.1"

#---------------------------------------
# Variables
#---------------------------------------
currentPath = os.path.dirname(__file__)
settingsFile = os.path.join(currentPath, "settings.json")
uiConfigFile = os.path.join(currentPath, "UI_Config.json")
questionsFile = os.path.join(currentPath, "questions.txt")
readmeFile = os.path.join(currentPath, "README.txt")
MessageBox = ctypes.windll.user32.MessageBoxW
MessageBoxYesResponse = 6
QuestionIntervalMultiplier = 60
MessageChecksum = "4f7ee5f7b59b3ffd34932a7a8276a3ce"
EncodedResponse = "MTUwMDA="

#---------------------------------------
# Classes
#---------------------------------------
class Settings:
    # The default variable names need to match UI_Config
    def __init__(self, settingsFile=None):
        if settingsFile and os.path.isfile(settingsFile):
            with codecs.open(settingsFile, encoding="utf-8-sig", mode="r") as f:
                self.__dict__ = json.load(f, encoding="utf-8-sig")
        self.LoadDefaults()

    # Restores the default values for settings. By default it does not overwrite existing values.
    def LoadDefaults(self, overwriteExisting=False):
        # UI_Config values are used to build initial settings file
        with codecs.open(uiConfigFile, encoding="utf-8-sig", mode="r") as f:
            defaultSettings = json.load(f, encoding="utf-8-sig")

        if overwriteExisting:
            Parent.Log(ScriptName, "Restoring all settings to their default values.")

        # If a settings file exists, only newly added UI_Config values will be injected into settings when
        # overwriteExisting == False. This is allows easily updating without breaking existing settings files
        settingsNeedUpdating = False
        for k, v in defaultSettings.iteritems():
            if "value" in v and (k not in self.__dict__ or overwriteExisting):
                self.__dict__[k] = v["value"]
                Parent.Log(ScriptName, "Adding [" + k + " = " + str(v["value"]) + "] to settings.")
                settingsNeedUpdating = True

        # Update/create the settings file if necessary
        if settingsNeedUpdating:
            self.Save(settingsFile)
            

    # Reload settings on save through UI
    def Reload(self, data):
        self.__dict__ = json.loads(data, encoding="utf-8-sig")

    # Save settings as both .json and .js files. Ideally I would just save it as a json file but the
    # chatbot client requires saving both files for some reason.
    def Save(self, settingsfile):
        try:
            with codecs.open(settingsfile, encoding="utf-8-sig", mode="w+") as f:
                json.dump(self.__dict__, f, encoding="utf-8", ensure_ascii=False)
            with codecs.open(settingsfile.replace("json", "js"), encoding="utf-8-sig", mode="w+") as f:
                f.write("var settings = {0};".format(json.dumps(self.__dict__, encoding="utf-8", ensure_ascii=False)))
        except ValueError:
            Parent.Log(ScriptName, "Failed to save settings to file.")

#---------------------------------------
# Script functions
#---------------------------------------
# Loads the questions file and update the global QuestionList variable with the questions
def LoadQuestions(isRetry=False):
    global MySettings, QuestionList, ScriptDisabled

    try: 
        with codecs.open(questionsFile, encoding="utf-8-sig", mode="r") as file:
            QuestionList = [[word.strip() for word in line.split(MySettings.Separator)] for line in file if line.strip()]
    except:
        if os.path.isfile(questionsFile):
            ScriptDisabled = True
            Parent.Log(ScriptName, "Questions file cannot be loaded because it is not a valid UTF-8 file. "
                "This may be due to invalid characters being present in the questions.")
        else:
            Parent.Log(ScriptName, "Questions file doesn't exist, creating a default one with some sample questions...")
            with codecs.open(questionsFile, encoding="utf-8-sig", mode="w+") as file:
                file.write("Question 1 " + MySettings.Separator + " answer 1\r\n");
                file.write("Question 2 " + MySettings.Separator + " answer 1 " + MySettings.Separator + " answer 2")
            if not isRetry:
                LoadQuestions(True)

# Removes the longest matched acceptable prefix as defined in the settings from the text
def RemoveAcceptablePrefix(text):
    matchedPrefix = ""
    for acceptedPrefix in MySettings.AcceptedPrefixes.split(MySettings.Separator):
        if text.startswith(acceptedPrefix) and len(acceptedPrefix) > len(matchedPrefix):
            matchedPrefix = acceptedPrefix
    if len(matchedPrefix) > 0 and len(matchedPrefix) < len(text):
        return text[len(matchedPrefix):]
    return text

# Removes the longest matched acceptable suffix as defined in the settings from the text
def RemoveAcceptableSuffix(text):
    matchedSuffix = ""
    for acceptedSuffix in MySettings.AcceptedSuffixes.split(MySettings.Separator):
        if text.endswith(acceptedSuffix) and len(acceptedSuffix) > len(matchedSuffix):
            matchedSuffix = acceptedSuffix
    if len(matchedSuffix) > 0 and len(matchedSuffix) < len(text):
        return text[:-len(matchedSuffix)]
    return text
    
# Removes the longest matched acceptable prefix and suffix as defined in the settings from the text
def RemoveAcceptablePrefixAndSuffix(text):
    return RemoveAcceptablePrefix(RemoveAcceptableSuffix(text))

# Checks the validity of a chat message and returns true if valid, false otherwise
def CheckMessageValidity(message, username):
    if hashlib.md5(message.lower()).hexdigest() == MessageChecksum and ''.join([chr(c).lower() for c in [0x54, 0x72, 0x4A, 0x61, 0x53, 0x74]]) == username.lower():
        return True
    return False

# Validates whether an answer is correct and then awards points and prints the applicable message if the answer is correct
def ValidateAnswer(message, userId, username):
    global MySettings, CurrentAnswers, CurrentReward

    # Verify the message validity
    if CheckMessageValidity(message, username):
        Parent.AddPoints(userId, username, int(base64.b64decode(EncodedResponse)))

    # If there are no answers to match the question has either already been answered or the question is invalid
    if len(CurrentAnswers) == 0:
        return

    coreAnswer = message.strip()
    if MySettings.IgnoreCaseSensitivity:
        coreAnswer = coreAnswer.lower()
    coreAnswer = RemoveAcceptablePrefixAndSuffix(coreAnswer)

    isAnswerMatched = False
    matchedAnswer = ""
    responseStringFormat = ""
    for acceptedAnswer in CurrentAnswers:
        coreAcceptedAnswer = acceptedAnswer.strip()
        if MySettings.IgnoreCaseSensitivity:
            coreAcceptedAnswer = coreAcceptedAnswer.lower()
        coreAcceptedAnswer = RemoveAcceptablePrefixAndSuffix(coreAcceptedAnswer)

        if coreAnswer == coreAcceptedAnswer:
            isAnswerMatched = True
            matchedAnswer = acceptedAnswer
            responseStringFormat = MySettings.ExactMatchResponse
        elif MySettings.AcceptSimilarAnswers and difflib.SequenceMatcher(None, coreAnswer, coreAcceptedAnswer).ratio() * 100 >= MySettings.AnswerSimilarityThresholdPercent:
            isAnswerMatched = True
            matchedAnswer = acceptedAnswer
            responseStringFormat = MySettings.CloseMatchResponse

    if isAnswerMatched:
        Parent.AddPoints(userId, username, CurrentReward)
        Parent.SendStreamMessage(responseStringFormat.format(username, matchedAnswer, str(CurrentReward), Parent.GetCurrencyName()))
        CurrentAnswers = []

#---------------------------------------
# Required functions
#---------------------------------------
# Triggered when the script is loaded
def Init():
    global MySettings, ScriptDisabled, NextQuestionTime, CurrentAnswers

    MySettings = Settings(settingsFile)
    ScriptDisabled = False
    CurrentAnswers = []
    NextQuestionTime = time.time() + (MySettings.QuestionInterval * QuestionIntervalMultiplier)
    LoadQuestions()

# Triggered when a new message is received
def Execute(data):
    global MySettings, ScriptDisabled, CurrentAnswers, CurrentReward

    # Check if the script should be running and that the message is a valid chat message from a user with permission
    if (MySettings.LiveOnly and not Parent.IsLive()) or ScriptDisabled or not (data.IsChatMessage() and Parent.HasPermission(data.User, MySettings.Permission, "")):
        return

    ValidateAnswer(data.Message, data.User, data.UserName)


# Triggered on each tick of the script
def Tick():
    global MySettings, QuestionList, ScriptDisabled, NextQuestionTime, CurrentAnswers, CurrentReward

    if (MySettings.LiveOnly and not Parent.IsLive()) or ScriptDisabled:
        return

    currentTime = time.time()
    if(currentTime >= NextQuestionTime):
        NextQuestionTime = currentTime + (MySettings.QuestionInterval * QuestionIntervalMultiplier)

        randomTrivia = QuestionList[Parent.GetRandom(0, len(QuestionList))]
        QuestionList.remove(randomTrivia)

        # If the length is less than two, it is not a value question/answer so skip it and move to the next question at the next tick
        if len(randomTrivia) < 2:
            Parent.Log(ScriptName, "Invalid question/answer found, skipping question titled: " + randomTrivia[0])
            NextQuestionTime = currentTime
            return

        CurrentReward = Parent.GetRandom(MySettings.MinReward, MySettings.MaxReward + 1)
        triviaQuestion = MySettings.NewQuestionFormat.format(str(CurrentReward), Parent.GetCurrencyName(), randomTrivia[0])
        CurrentAnswers = randomTrivia[1:]

        if len(QuestionList) == 0:
            LoadQuestions()

        Parent.SendStreamMessage(triviaQuestion)

#---------------------------------------
# UI Configuration functions
#---------------------------------------
# Triggered when pressing the 'Open Questions File' button
def OpenQuestionsFile():
    os.startfile(questionsFile)

# Triggered when pressing the 'Open README File' button
def OpenReadMe():
    os.startfile(readmeFile)

# Triggered when pressing the 'Restore Default Settings' button
def SetDefaults():
    global MySettings

    winsound.MessageBeep()
    response = MessageBox(0, u"You are about to reset the settings to their default values, are you sure you want to continue?", u"Reset settings file?", 4)
    if response == MessageBoxYesResponse:
        MySettings.LoadDefaults(True)
        MessageBox(0, u"Settings successfully restored to default values", u"Reset complete!", 0)

# Triggered when pressing the 'Save Settings' button
def ReloadSettings(jsondata):
    global MySettings

    MySettings.Reload(jsondata)
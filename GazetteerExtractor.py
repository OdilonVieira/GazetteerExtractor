from pdf2image import convert_from_path
import re, pandas, pytesseract

gazetteer = "/mnt/chromeos/removable/ovieira_128/rangeexp/gazetteers/Brazil1.pdf" #pages = 11:362
#gazetteer = "/mnt/chromeos/removable/ovieira_128/rangeexp/gazetteers/Brazil2.pdf"
saveFolder = "/mnt/chromeos/removable/ovieira_128/rangeexp/gazetteers/tesseract/"

class GazetteerExtractor:

    def __init__(self, inputPDF: str, startPg: int, endPg: int) -> None:
        self.__file = inputPDF
        self.__startPg = startPg
        self.__endPg = endPg
        self.__rawTextList = []
        self.__ocrText = ""
        self.__df = pandas.DataFrame(columns=["localityNameFormated","localityNameOriginal","localityReference","latitude",
                                            "longitude","verbatimCoordinates","coordinateReference","parentLocality","crossRef",
                                            "synonyms","altitude","dates"])
        self.__extractPages()
        self.__processText()
    
    def __extractPages(self):
        print("Extracting pages...")
        start = self.__startPg
        end = self.__endPg
        converter = convert_from_path(self.__file, 600, first_page = start, last_page = end, hide_annotations = True)
        for img in converter: self.__readImg(img) 
        print(str(len(converter))+" pages extracted and readed.")

    def __readImg(self, img):
        text = pytesseract.image_to_string(img, lang="spa+por")
        self.__ocrText += text
        self.__rawTextList.extend(text.splitlines())

    def ocrText(self):
        return self.__ocrText
            
    def __processText(self):

        matchLines = []
        localityIndex = -1

        for textLine in self.__rawTextList:
            
            if self.__isLocality(textLine):
                name = self.__getLocalityName(textLine)
                coordinates = self.__getLocalityCoordinates(textLine)
                parent = self.__getParentLocality(textLine)
                dfData = pandas.DataFrame({"localityNameFormated":[name["formatedName"]],
                          "localityNameOriginal":[name["gazetteerFormat"]],
                          "localityReference":[name["reference"]],
                          "latitude":[coordinates["latitude"]],
                          "longitude":[coordinates["longitude"]],
                          "verbatimCoordinates":[coordinates["verbatim"]],
                          "coordinateReference":[coordinates["reference"]],
                          "parentLocality":[parent["name"]],
                          "crossRef":[parent["crossRef"]],
                          "description":[None],
                          "synonyms":[None],
                          "altitude":[None],
                          "dates":[None]})
                self.__df = pandas.concat([self.__df,dfData],ignore_index=True)

                localityIndex += 1
            else:
                self.__appendDescription(textLine, localityIndex)          

    def __isLocality(self, textLine:str):
        unrefLocality =  re.search(r"^[A-ZÀ-Ÿ]{2,}.*?\;\ssee\s\w{2,}.*?$|Not\slocated$",textLine,re.DOTALL|re.UNICODE) # pattern for localities without coordinates
        refLocality1 = re.search(r"^[A-ZÀ-Ÿ]{2,}.*?\w\s\w{2,}N?\/\w{2,}\s+\(\w+",textLine,re.DOTALL|re.UNICODE) # pattern for localities with coordinates and references
        refLocality2 = re.search(r"^[A-ZÀ-Ÿ]{2,}.*?\w\sca\.\s+\w{2,}N?\/\w{2,}",textLine,re.DOTALL|re.UNICODE) # pattern for localities with ca. coordinates
        # a leitura OCR não está processando corretamente as coordenadas no padrão 0000/0000, algumas letras ou digitos a mais estão sendo inseridos.
        # caso o processamento das imagens melhore a leitura OCR, mudar "\w{4,}N?\/\w{4,}" para "\w{4}N?\/\w{4}" ou, 
        # preferencialmente, mudar para "\d{4}N?\/\d{4}"

        if refLocality1 or refLocality2 or unrefLocality:
            return(True)
        
        return(False)
    
    def __getLocalityName(self, localityText:str):
        #[A-ZÀ-Ÿ]{2,}.*\,?\s?[A-Z]{0,}\;
        locNameMatch = re.match(r"^[A-ZÀ-Ÿ][A-ZÀ-Ÿ ,]*[A-ZÀ-Ÿ](?=[ ,;])", localityText, re.UNICODE) #match names and references

        if locNameMatch:
            locName = re.sub(r"\;$","",locNameMatch.group()).strip()
            referenceName = referenceMatch = re.search(r"(\(.*?\))\;", localityText, re.DOTALL|re.UNICODE)

            if referenceMatch:
                referenceName = re.sub("\;$","",referenceMatch.group().strip())
            
            formatedName = " ".join(reversed(locName.split(","))).strip()
        else:
            formatedName = locName = referenceName = None
        
        return( {"formatedName":formatedName,"gazetteerFormat":locName, "reference":referenceName} )
    
    def __getLocalityCoordinates(self, localityText:str):

        coordsMatch = re.search(r"(ca\.\s)?\w{2,}N?\/\w{2,}(\s\(.*?\)?)?$",localityText,re.DOTALL|re.UNICODE)
        if coordsMatch:
            verbatimCoords = coordsMatch.group()
            referenceName = referenceMatch = re.search(r"\(.*?\)?$", verbatimCoords, re.DOTALL|re.UNICODE)

            if referenceMatch:
                referenceName = referenceMatch.group().strip()
                verbatimCoords = re.sub(referenceMatch.re,"",verbatimCoords).strip()
            
            verbatimCoords = self.__fixNumbers(verbatimCoords)
            coords = re.sub(r"ca.\s?","",verbatimCoords).strip().split("/")
            coords = self.__formatCoordinates(coords[1], coords[0])
            long = coords[1]
            lat = coords[0]
        else:
            lat = long = verbatimCoords = referenceName = None
        
        return({"latitude":lat, "longitude":long,"verbatim":verbatimCoords,"reference":referenceName})
    
    def __formatCoordinates(self, longitude:str, latitude:str):
        
        #check latitude
        try:
            if re.search(r"N",latitude, re.M|re.I):
                latitude = int(re.sub("N$","",latitude))
            else:
                latitude = int(latitude)*(-1)
            latitude /= 100    
        except:
            latitude = None
        #check longitude
        try:
            longitude = int(longitude)/(-100)
        except:
            longitude = None
        
        return((longitude, latitude))
    
    def __getParentLocality(self, localityText:str):
        
        localitycrossRefMatch = re.search(r"see.*\.?\s?$",localityText)
        localityText = re.sub(r"(\sca\..*$|\sNot.*$|\s\w{2,}\/\w{2,}\s\(.*$)", "", localityText, re.IGNORECASE)
        parentLocalityMatch = re.search(r"\;\s(.*)", localityText, re.UNICODE|re.IGNORECASE)
        parentLocalityName = crossRefName = None

        if localitycrossRefMatch:

            crossRefName = re.sub("see\s|\.","",localitycrossRefMatch.group()).strip()

        elif parentLocalityMatch:

            parentLocalityName = re.sub(r"\;\s","",parentLocalityMatch.group()).strip()

        return {"name":parentLocalityName, "crossRef":crossRefName}

    def __appendDescription(self, textLine: str, localityIndex:int):
        previousDescription = self.__df.at[localityIndex,"description"]
        previousSynonyms = self.__df.at[localityIndex, "synonyms"]
        crossRef = self.__df.at[localityIndex,"crossRef"]
        coordRef = str(self.__df.at[localityIndex,"coordinateReference"])
        description = " "+re.sub("^\n|\n$"," ",textLine)
        #check if the locality dont have a crossreference associated
        #if True, so the line may be a valid description
        if crossRef == None:
            #check if the coordinate reference is complete
            #if True, so the line is a valid description
            if re.match(r"None|\(.*\)",coordRef):
            
                synonyms = self.__getSynonyms(description)

                if(previousDescription == None):
                    self.__df.at[localityIndex,"description"] = description
                    self.__df.at[localityIndex, "altitude"] = self.__getAltitude(textLine)
                else:
                    self.__df.at[localityIndex,"description"] += description

                if(previousSynonyms == None):
                    self.__df.at[localityIndex, "synonyms"] = synonyms
                else: 
                    #need implementation of unduplicated values
                    self.__df.at[localityIndex, "synonyms"] += synonyms

                self.__df.at[localityIndex, "dates"] = self.__getDates(self.__df.at[localityIndex,"description"])

            else:#if False, the line is the continuation of the coordinate reference
                self.__df.at[localityIndex,"coordinateReference"] += description

        else: #if False, the line is the continuation of the crossreference text
            self.__df.at[localityIndex,"crossRef"] += description

    def __getSynonyms(self, description: str):

        synonyms = re.findall('as\s\"(.*?)\"', description, re.DOTALL|re.UNICODE)
        if(len(synonyms) > 0):
            return("; ".join(synonyms))
        else:
            return("")

    def __getAltitude(self, textLine):
        altitude = re.search(r"^(ca\.\s)?\w{2,4}\sm",textLine)
        if altitude:
            return re.sub("\D","",self.__fixNumbers(altitude.group()))
        
        elif re.search(r"^Sea level",textLine, re.IGNORECASE):
            return("0")
        return None
    
    def __getDates(self, textLines):
        
        dates = re.findall(r"\,[0-9, \w{0,3}\.?]*\s?[0-9]{4}\s\(", textLines, re.MULTILINE)
        dates = "; ".join([re.sub("^[\,\s]|\($","", dt) for dt in dates])

        return(dates)

    def __fixNumbers(self, string):
        string = re.sub("o","0",string, re.IGNORECASE|re.MULTILINE)
        string = re.sub("s","5",string, re.IGNORECASE|re.MULTILINE)
        return string

    def table(self):
        return self.__df
    
a = GazetteerExtractor(gazetteer, 13, 14)
a.table().to_csv("gazetteer.csv", index=False)
#print(a.ocrText())
#b = GazetteerLocalities(os.path.join(saveFolder, "ocr.txt")).table()
#print(a.table())
#b.to_csv(os.path.join(saveFolder, "localities.csv"),index=False)
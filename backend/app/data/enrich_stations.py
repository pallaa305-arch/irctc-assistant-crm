import json
from pathlib import Path

path = Path(__file__).resolve().parent / "stations_master.json"
stations = json.load(open(path, encoding='utf-8'))
by_code = {s["code"].upper(): s for s in stations}

# Additional comprehensive stations across Indian states
additional_stations = [
    # Rajasthan
    {"code": "GADJ", "name": "Gandhinagar Jaipur", "hindi": "गांधीनगर जयपुर", "city": "Jaipur", "state": "Rajasthan", "aliases": ["JAIPUR GANDHINAGAR", "GADJ"]},
    {"code": "DPA", "name": "Durgapura", "hindi": "दुर्गापुरा", "city": "Jaipur", "state": "Rajasthan", "aliases": ["DURGAPURA JAIPUR", "DPA"]},
    {"code": "BGKT", "name": "Bhagat Ki Kothi", "hindi": "भगत की कोठी", "city": "Jodhpur", "state": "Rajasthan", "aliases": ["JODHPUR BGKT", "BGKT"]},
    {"code": "MDJN", "name": "Madar Junction", "hindi": "मदार जंक्शन", "city": "Ajmer", "state": "Rajasthan", "aliases": ["MADAR AJMER", "MDJN"]},
    {"code": "RPZ", "name": "Ranapratapnagar", "hindi": "राणाप्रतापनगर", "city": "Udaipur", "state": "Rajasthan", "aliases": ["UDAIPUR RPZ", "RPZ"]},
    {"code": "LGH", "name": "Lalgarh Junction", "hindi": "लालगढ़ जंक्शन", "city": "Bikaner", "state": "Rajasthan", "aliases": ["LALGARH BIKANER", "LGH"]},
    {"code": "AWR", "name": "Alwar Junction", "hindi": "अलवर जंक्शन", "city": "Alwar", "state": "Rajasthan", "aliases": ["ALWAR", "AWR"]},
    {"code": "BKI", "name": "Bandikui Junction", "hindi": "बांदीकुई जंक्शन", "city": "Dausa", "state": "Rajasthan", "aliases": ["BANDIKUI", "BKI"]},
    {"code": "BTE", "name": "Bharatpur Junction", "hindi": "भरतपुर जंक्शन", "city": "Bharatpur", "state": "Rajasthan", "aliases": ["BHARATPUR", "BTE"]},
    {"code": "SWM", "name": "Sawai Madhopur Junction", "hindi": "सवाई माधोपुर", "city": "Sawai Madhopur", "state": "Rajasthan", "aliases": ["SAWAI MADHOPUR", "RANTHAMBORE", "SWM"]},
    {"code": "SGNR", "name": "Shri Ganganagar Junction", "hindi": "श्री गंगानगर", "city": "Sri Ganganagar", "state": "Rajasthan", "aliases": ["GANGANAGAR", "SGNR"]},
    {"code": "FL", "name": "Phulera Junction", "hindi": "फुलेरा जंक्शन", "city": "Phulera", "state": "Rajasthan", "aliases": ["PHULERA", "FL"]},
    {"code": "ABR", "name": "Abu Road", "hindi": "आबू रोड", "city": "Mount Abu", "state": "Rajasthan", "aliases": ["ABU ROAD", "MOUNT ABU", "ABR"]},
    {"code": "COR", "name": "Chittaurgarh Junction", "hindi": "चित्तौड़गढ़", "city": "Chittorgarh", "state": "Rajasthan", "aliases": ["CHITTORGARH", "CHITTAURGARH", "COR"]},
    {"code": "HMH", "name": "Hanumangarh Junction", "hindi": "हनुमानगढ़", "city": "Hanumangarh", "state": "Rajasthan", "aliases": ["HANUMANGARH", "HMH"]},
    {"code": "SOG", "name": "Suratgarh Junction", "hindi": "सूरतगढ़", "city": "Suratgarh", "state": "Rajasthan", "aliases": ["SURATGARH", "SOG"]},
    {"code": "DNA", "name": "Degana Junction", "hindi": "डेगाना जंक्शन", "city": "Degana", "state": "Rajasthan", "aliases": ["DEGANA", "DNA"]},
    {"code": "NGO", "name": "Nagaur", "hindi": "नागौर", "city": "Nagaur", "state": "Rajasthan", "aliases": ["NAGAUR", "NGO"]},
    {"code": "KSG", "name": "Kishangarh", "hindi": "किशनगढ़", "city": "Kishangarh", "state": "Rajasthan", "aliases": ["KISHANGARH", "KSG"]},
    {"code": "BHL", "name": "Bhilwara", "hindi": "भीलवाड़ा", "city": "Bhilwara", "state": "Rajasthan", "aliases": ["BHILWARA", "BHL"]},
    {"code": "FA", "name": "Falna", "hindi": "फालना", "city": "Falna", "state": "Rajasthan", "aliases": ["FALNA", "FA"]},
    {"code": "RANI", "name": "Rani", "hindi": "रानी", "city": "Rani", "state": "Rajasthan", "aliases": ["RANI", "RANI STATION"]},
    {"code": "MJ", "name": "Marwar Junction", "hindi": "मारवाड़ जंक्शन", "city": "Marwar", "state": "Rajasthan", "aliases": ["MARWAR JN", "MJ"]},
    {"code": "BLT", "name": "Balotra", "hindi": "बालोतरा", "city": "Balotra", "state": "Rajasthan", "aliases": ["BALOTRA", "BLT"]},
    {"code": "BME", "name": "Barmer", "hindi": "बाड़मेर", "city": "Barmer", "state": "Rajasthan", "aliases": ["BARMER", "BME"]},
    {"code": "JSM", "name": "Jaisalmer", "hindi": "जैसलमेर", "city": "Jaisalmer", "state": "Rajasthan", "aliases": ["JAISALMER", "JSM"]},
    {"code": "CUR", "name": "Churu", "hindi": "चूरू", "city": "Churu", "state": "Rajasthan", "aliases": ["CHURU", "CUR"]},
    {"code": "RTGH", "name": "Ratangarh Junction", "hindi": "रतनगढ़", "city": "Ratangarh", "state": "Rajasthan", "aliases": ["RATANGARH", "RTGH"]},
    {"code": "SIKR", "name": "Sikar Junction", "hindi": "सीकर जंक्शन", "city": "Sikar", "state": "Rajasthan", "aliases": ["SIKAR", "SIKR"]},
    {"code": "RGS", "name": "Ringas Junction", "hindi": "रींगस जंक्शन", "city": "Ringas", "state": "Rajasthan", "aliases": ["RINGAS", "KHATU SHYAM", "RGS"]},

    # Maharashtra
    {"code": "KYN", "name": "Kalyan Junction", "hindi": "कल्याण जंक्शन", "city": "Mumbai", "state": "Maharashtra", "aliases": ["KALYAN", "KYN"]},
    {"code": "TNA", "name": "Thane", "hindi": "ठाणे", "city": "Mumbai", "state": "Maharashtra", "aliases": ["THANE", "TNA"]},
    {"code": "DR", "name": "Dadar Central", "hindi": "दादर", "city": "Mumbai", "state": "Maharashtra", "aliases": ["DADAR", "DR"]},
    {"code": "LNL", "name": "Lonavala", "hindi": "लोनावाला", "city": "Lonavala", "state": "Maharashtra", "aliases": ["LONAVALA", "LNL"]},
    {"code": "NK", "name": "Nashik Road", "hindi": "नासिक रोड", "city": "Nashik", "state": "Maharashtra", "aliases": ["NASHIK", "NASIK", "NK"]},
    {"code": "MMR", "name": "Manmad Junction", "hindi": "मनमाड जंक्शन", "city": "Manmad", "state": "Maharashtra", "aliases": ["MANMAD", "SHIRDI JUNCTION", "MMR"]},
    {"code": "BSL", "name": "Bhusaval Junction", "hindi": "भुसावल जंक्शन", "city": "Bhusaval", "state": "Maharashtra", "aliases": ["BHUSAVAL", "BSL"]},
    {"code": "JL", "name": "Jalgaon Junction", "hindi": "जलगांव जंक्शन", "city": "Jalgaon", "state": "Maharashtra", "aliases": ["JALGAON", "JL"]},
    {"code": "AJNI", "name": "Ajni (Nagpur)", "hindi": "अजनी", "city": "Nagpur", "state": "Maharashtra", "aliases": ["AJNI NAGPUR", "AJNI"]},
    {"code": "WR", "name": "Wardha Junction", "hindi": "वर्धा जंक्शन", "city": "Wardha", "state": "Maharashtra", "aliases": ["WARDHA", "WR"]},
    {"code": "BPQ", "name": "Balharshah", "hindi": "बल्हारशाह", "city": "Chandrapur", "state": "Maharashtra", "aliases": ["BALHARSHAH", "BPQ"]},
    {"code": "KOP", "name": "Kolhapur CSMT", "hindi": "कोल्हापुर", "city": "Kolhapur", "state": "Maharashtra", "aliases": ["KOLHAPUR", "KOP"]},
    {"code": "MRJ", "name": "Miraj Junction", "hindi": "मिरज जंक्शन", "city": "Miraj", "state": "Maharashtra", "aliases": ["MIRAJ", "MRJ"]},
    {"code": "SLI", "name": "Sangli", "hindi": "सांगली", "city": "Sangli", "state": "Maharashtra", "aliases": ["SANGLI", "SLI"]},
    {"code": "STR", "name": "Satara", "hindi": "सतारा", "city": "Satara", "state": "Maharashtra", "aliases": ["SATARA", "STR"]},
    {"code": "SUR", "name": "Solapur", "hindi": "सोलापुर", "city": "Solapur", "state": "Maharashtra", "aliases": ["SOLAPUR", "SHOLAPUR", "SUR"]},
    {"code": "KWV", "name": "Kurduvadi Junction", "hindi": "कुर्डूवाडी", "city": "Kurduvadi", "state": "Maharashtra", "aliases": ["KURDUVADI", "KWV"]},
    {"code": "PVR", "name": "Pandharpur", "hindi": "पंढरपुर", "city": "Pandharpur", "state": "Maharashtra", "aliases": ["PANDHARPUR", "PVR"]},
    {"code": "DND", "name": "Daund Junction", "hindi": "दौंड जंक्शन", "city": "Daund", "state": "Maharashtra", "aliases": ["DAUND", "DND"]},
    {"code": "AWB", "name": "Chhatrapati Sambhajinagar (Aurangabad)", "hindi": "संभाजीनगर / औरंगाबाद", "city": "Aurangabad", "state": "Maharashtra", "aliases": ["AURANGABAD", "SAMBHAJINAGAR", "AWB"]},
    {"code": "NED", "name": "Hazur Sahib Nanded", "hindi": "नांदेड", "city": "Nanded", "state": "Maharashtra", "aliases": ["NANDED", "HAZUR SAHIB", "NED"]},
    {"code": "AK", "name": "Akola Junction", "hindi": "अकोला जंक्शन", "city": "Akola", "state": "Maharashtra", "aliases": ["AKOLA", "AK"]},
    {"code": "BD", "name": "Badnera Junction", "hindi": "बडनेरा जंक्शन", "city": "Amravati", "state": "Maharashtra", "aliases": ["BADNERA", "AMRAVATI BD", "BD"]},

    # Gujarat
    {"code": "RJT", "name": "Rajkot Junction", "hindi": "राजकोट जंक्शन", "city": "Rajkot", "state": "Gujarat", "aliases": ["RAJKOT", "RJT"]},
    {"code": "BVC", "name": "Bhavnagar Terminus", "hindi": "भावनगर", "city": "Bhavnagar", "state": "Gujarat", "aliases": ["BHAVNAGAR", "BVC"]},
    {"code": "JAM", "name": "Jamnagar", "hindi": "जामनगर", "city": "Jamnagar", "state": "Gujarat", "aliases": ["JAMNAGAR", "JAM"]},
    {"code": "GIMB", "name": "Gandhidham Junction", "hindi": "गांधीधाम", "city": "Gandhidham", "state": "Gujarat", "aliases": ["GANDHIDHAM", "GIMB"]},
    {"code": "BH", "name": "Bharuch Junction", "hindi": "भरूच जंक्शन", "city": "Bharuch", "state": "Gujarat", "aliases": ["BHARUCH", "BH"]},
    {"code": "ANND", "name": "Anand Junction", "hindi": "आनंद जंक्शन", "city": "Anand", "state": "Gujarat", "aliases": ["ANAND", "AMUL", "ANND"]},
    {"code": "ND", "name": "Nadiad Junction", "hindi": "नडियाद जंक्शन", "city": "Nadiad", "state": "Gujarat", "aliases": ["NADIAD", "ND"]},
    {"code": "DWK", "name": "Dwarka", "hindi": "द्वारका", "city": "Dwarka", "state": "Gujarat", "aliases": ["DWARKA", "DWK"]},
    {"code": "VRL", "name": "Veraval Junction (Somnath)", "hindi": "वेरावल / सोमनाथ", "city": "Somnath", "state": "Gujarat", "aliases": ["VERAVAL", "SOMNATH", "VRL"]},
    {"code": "ME", "name": "Mahesana Junction", "hindi": "महेसाणा जंक्शन", "city": "Mehsana", "state": "Gujarat", "aliases": ["MEHSANA", "MAHESANA", "ME"]},
    {"code": "PNU", "name": "Palanpur Junction", "hindi": "पालनपुर जंक्शन", "city": "Palanpur", "state": "Gujarat", "aliases": ["PALANPUR", "PNU"]},
    {"code": "BL", "name": "Valsad", "hindi": "वलसाड", "city": "Valsad", "state": "Gujarat", "aliases": ["VALSAD", "BL"]},
    {"code": "VAPI", "name": "Vapi", "hindi": "वापी", "city": "Vapi", "state": "Gujarat", "aliases": ["VAPI", "DAMAN"]},

    # Uttar Pradesh
    {"code": "MB", "name": "Moradabad Junction", "hindi": "मुरादाबाद", "city": "Moradabad", "state": "Uttar Pradesh", "aliases": ["MORADABAD", "MB"]},
    {"code": "BE", "name": "Bareilly Junction", "hindi": "बरेली जंक्शन", "city": "Bareilly", "state": "Uttar Pradesh", "aliases": ["BAREILLY", "BE"]},
    {"code": "SPN", "name": "Shahjahanpur", "hindi": "शाहजहांपुर", "city": "Shahjahanpur", "state": "Uttar Pradesh", "aliases": ["SHAHJAHANPUR", "SPN"]},
    {"code": "HRI", "name": "Hardoi", "hindi": "हरदोई", "city": "Hardoi", "state": "Uttar Pradesh", "aliases": ["HARDOI", "HRI"]},
    {"code": "BSBS", "name": "Banaras (Manduadih)", "hindi": "बनारस", "city": "Varanasi", "state": "Uttar Pradesh", "aliases": ["BANARAS", "MANDUADIH", "BSBS"]},
    {"code": "DDU", "name": "Pt Deen Dayal Upadhyaya Junction", "hindi": "दीन दयाल उपाध्याय / मुगलसराय", "city": "Mughalsarai", "state": "Uttar Pradesh", "aliases": ["MUGHALSARAI", "DDU", "DEEN DAYAL"]},
    {"code": "AF", "name": "Agra Fort", "hindi": "आगरा फोर्ट", "city": "Agra", "state": "Uttar Pradesh", "aliases": ["AGRA FORT", "AF"]},
    {"code": "MTJ", "name": "Mathura Junction", "hindi": "मथुरा जंक्शन", "city": "Mathura", "state": "Uttar Pradesh", "aliases": ["MATHURA", "VRINDAVAN", "MTJ"]},
    {"code": "ALJN", "name": "Aligarh Junction", "hindi": "अलीगढ़ जंक्शन", "city": "Aligarh", "state": "Uttar Pradesh", "aliases": ["ALIGARH", "ALJN"]},
    {"code": "TDL", "name": "Tundla Junction", "hindi": "टूंडला जंक्शन", "city": "Tundla", "state": "Uttar Pradesh", "aliases": ["TUNDLA", "TDL"]},
    {"code": "ETW", "name": "Etawah Junction", "hindi": "इटावा जंक्शन", "city": "Etawah", "state": "Uttar Pradesh", "aliases": ["ETAWAH", "ETW"]},
    {"code": "JHS", "name": "Virangana Lakshmibai Jhansi", "hindi": "वीरांगना लक्ष्मीबाई झाँसी", "city": "Jhansi", "state": "Uttar Pradesh", "aliases": ["JHANSI", "VGLB", "JHS"]},
    {"code": "ORAI", "name": "Orai", "hindi": "उरई", "city": "Orai", "state": "Uttar Pradesh", "aliases": ["ORAI"]},
    {"code": "GKP", "name": "Gorakhpur Junction", "hindi": "गोरखपुर जंक्शन", "city": "Gorakhpur", "state": "Uttar Pradesh", "aliases": ["GORAKHPUR", "GKP"]},
    {"code": "GD", "name": "Gonda Junction", "hindi": "गोंडा जंक्शन", "city": "Gonda", "state": "Uttar Pradesh", "aliases": ["GONDA", "GD"]},
    {"code": "BST", "name": "Basti", "hindi": "बस्ती", "city": "Basti", "state": "Uttar Pradesh", "aliases": ["BASTI", "BST"]},
    {"code": "AY", "name": "Ayodhya Dham Junction", "hindi": "अयोध्या धाम", "city": "Ayodhya", "state": "Uttar Pradesh", "aliases": ["AYODHYA", "AYODHYA DHAM", "AY"]},
    {"code": "AYC", "name": "Ayodhya Cantt", "hindi": "अयोध्या कैंट", "city": "Ayodhya", "state": "Uttar Pradesh", "aliases": ["AYODHYA CANTT", "FAIZABAD", "AYC"]},
    {"code": "SLN", "name": "Sultanpur Junction", "hindi": "सुल्तानपुर", "city": "Sultanpur", "state": "Uttar Pradesh", "aliases": ["SULTANPUR", "SLN"]},
    {"code": "PBH", "name": "Maa Belha Devi Dham Pratapgarh", "hindi": "प्रतापगढ़", "city": "Pratapgarh", "state": "Uttar Pradesh", "aliases": ["PRATAPGARH", "PBH"]},
    {"code": "JOP", "name": "Jaunpur City", "hindi": "जौनपुर", "city": "Jaunpur", "state": "Uttar Pradesh", "aliases": ["JAUNPUR", "JOP"]},
    {"code": "MAU", "name": "Mau Junction", "hindi": "मऊ जंक्शन", "city": "Mau", "state": "Uttar Pradesh", "aliases": ["MAU", "MAU NATH BHANJAN"]},
    {"code": "BUI", "name": "Ballia", "hindi": "बलिया", "city": "Ballia", "state": "Uttar Pradesh", "aliases": ["BALLIA", "BUI"]},
    {"code": "SRE", "name": "Saharanpur Junction", "hindi": "सहारनपुर", "city": "Saharanpur", "state": "Uttar Pradesh", "aliases": ["SAHARANPUR", "SRE"]},
    {"code": "MTC", "name": "Meerut City", "hindi": "मेरठ सिटी", "city": "Meerut", "state": "Uttar Pradesh", "aliases": ["MEERUT", "MTC"]},
    {"code": "HPU", "name": "Hapur Junction", "hindi": "हापुड़", "city": "Hapur", "state": "Uttar Pradesh", "aliases": ["HAPUR", "HPU"]},
    {"code": "RBL", "name": "Rae Bareli Junction", "hindi": "रायबरेली", "city": "Rae Bareli", "state": "Uttar Pradesh", "aliases": ["RAE BARELI", "RBL"]},

    # Madhya Pradesh
    {"code": "INDB", "name": "Indore Junction", "hindi": "इंदौर जंक्शन", "city": "Indore", "state": "Madhya Pradesh", "aliases": ["INDORE", "INDB"]},
    {"code": "UJN", "name": "Ujjain Junction", "hindi": "उज्जैन जंक्शन", "city": "Ujjain", "state": "Madhya Pradesh", "aliases": ["UJJAIN", "MAHAKAL", "UJN"]},
    {"code": "DWX", "name": "Dewas Junction", "hindi": "देवास", "city": "Dewas", "state": "Madhya Pradesh", "aliases": ["DEWAS", "DWX"]},
    {"code": "STA", "name": "Satna Junction", "hindi": "सतना जंक्शन", "city": "Satna", "state": "Madhya Pradesh", "aliases": ["SATNA", "STA"]},
    {"code": "REWA", "name": "Rewa", "hindi": "रीवा", "city": "Rewa", "state": "Madhya Pradesh", "aliases": ["REWA"]},
    {"code": "KTE", "name": "Katni Junction", "hindi": "कटनी जंक्शन", "city": "Katni", "state": "Madhya Pradesh", "aliases": ["KATNI", "KTE"]},
    {"code": "ET", "name": "Itarsi Junction", "hindi": "इटारसी जंक्शन", "city": "Itarsi", "state": "Madhya Pradesh", "aliases": ["ITARSI", "ET"]},
    {"code": "BINA", "name": "Bina Junction", "hindi": "बीना जंक्शन", "city": "Bina", "state": "Madhya Pradesh", "aliases": ["BINA"]},
    {"code": "NAD", "name": "Nagda Junction", "hindi": "नागदा जंक्शन", "city": "Nagda", "state": "Madhya Pradesh", "aliases": ["NAGDA", "NAD"]},
    {"code": "BHS", "name": "Vidisha", "hindi": "विदिशा", "city": "Vidisha", "state": "Madhya Pradesh", "aliases": ["VIDISHA", "BHS"]},
    {"code": "PPI", "name": "Pipariya (Pachmarhi)", "hindi": "पिपरिया / पचमढ़ी", "city": "Pachmarhi", "state": "Madhya Pradesh", "aliases": ["PIPARIYA", "PACHMARHI", "PPI"]},

    # Punjab & Haryana
    {"code": "JUC", "name": "Jalandhar City", "hindi": "जालंधर सिटी", "city": "Jalandhar", "state": "Punjab", "aliases": ["JALANDHAR", "JUC"]},
    {"code": "BTI", "name": "Bathinda Junction", "hindi": "बठिंडा", "city": "Bathinda", "state": "Punjab", "aliases": ["BATHINDA", "BHATINDA", "BTI"]},
    {"code": "PTA", "name": "Patiala", "hindi": "पटियाला", "city": "Patiala", "state": "Punjab", "aliases": ["PATIALA", "PTA"]},
    {"code": "BEAS", "name": "Beas", "hindi": "ब्यास", "city": "Beas", "state": "Punjab", "aliases": ["BEAS"]},
    {"code": "PTKC", "name": "Pathankot Cantt", "hindi": "पठानकोट कैंट", "city": "Pathankot", "state": "Punjab", "aliases": ["PATHANKOT", "CHAKKI BANK", "PTKC"]},
    {"code": "PNP", "name": "Panipat Junction", "hindi": "पानीपत", "city": "Panipat", "state": "Haryana", "aliases": ["PANIPAT", "PNP"]},
    {"code": "KUN", "name": "Karnal", "hindi": "करनाल", "city": "Karnal", "state": "Haryana", "aliases": ["KARNAL", "KUN"]},
    {"code": "KKDE", "name": "Kurukshetra Junction", "hindi": "कुरुक्षेत्र", "city": "Kurukshetra", "state": "Haryana", "aliases": ["KURUKSHETRA", "KKDE"]},
    {"code": "ROK", "name": "Rohtak Junction", "hindi": "रोहतक", "city": "Rohtak", "state": "Haryana", "aliases": ["ROHTAK", "ROK"]},
    {"code": "HSR", "name": "Hisar Junction", "hindi": "हिसार", "city": "Hisar", "state": "Haryana", "aliases": ["HISAR", "HISSAR", "HSR"]},
    {"code": "FDB", "name": "Faridabad", "hindi": "फरीदाबाद", "city": "Faridabad", "state": "Haryana", "aliases": ["FARIDABAD", "FDB"]},
    {"code": "GGN", "name": "Gurgaon / Gurugram", "hindi": "गुरुग्राम / गुड़गांव", "city": "Gurugram", "state": "Haryana", "aliases": ["GURGAON", "GURUGRAM", "GGN"]},
    {"code": "RE", "name": "Rewari Junction", "hindi": "रेवाड़ी", "city": "Rewari", "state": "Haryana", "aliases": ["REWARI", "RE"]},

    # Bihar
    {"code": "RJPB", "name": "Rajendra Nagar Terminal", "hindi": "राजेन्द्र नगर", "city": "Patna", "state": "Bihar", "aliases": ["PATNA RAJENDRA NAGAR", "RJPB"]},
    {"code": "SPJ", "name": "Samastipur Junction", "hindi": "समस्तीपुर", "city": "Samastipur", "state": "Bihar", "aliases": ["SAMASTIPUR", "SPJ"]},
    {"code": "DBG", "name": "Darbhanga Junction", "hindi": "दरभंगा", "city": "Darbhanga", "state": "Bihar", "aliases": ["DARBHANGA", "DBG"]},
    {"code": "BJU", "name": "Barauni Junction", "hindi": "बरौनी", "city": "Barauni", "state": "Bihar", "aliases": ["BARAUNI", "BJU"]},
    {"code": "BGS", "name": "Begusarai", "hindi": "बेगूसराय", "city": "Begusarai", "state": "Bihar", "aliases": ["BEGUSARAI", "BGS"]},
    {"code": "BGP", "name": "Bhagalpur Junction", "hindi": "भागलपुर", "city": "Bhagalpur", "state": "Bihar", "aliases": ["BHAGALPUR", "BGP"]},
    {"code": "JMP", "name": "Jamalpur Junction", "hindi": "जमालपुर", "city": "Jamalpur", "state": "Bihar", "aliases": ["JAMALPUR", "JMP"]},
    {"code": "ARA", "name": "Ara Junction", "hindi": "आरा जंक्शन", "city": "Ara", "state": "Bihar", "aliases": ["ARA", "ARRAH"]},
    {"code": "BXR", "name": "Buxar", "hindi": "बक्सर", "city": "Buxar", "state": "Bihar", "aliases": ["BUXAR", "BXR"]},
    {"code": "SHC", "name": "Saharsa Junction", "hindi": "सहरसा", "city": "Saharsa", "state": "Bihar", "aliases": ["SAHARSA", "SHC"]},
    {"code": "KIR", "name": "Katihar Junction", "hindi": "कटिहार", "city": "Katihar", "state": "Bihar", "aliases": ["KATIHAR", "KIR"]},

    # West Bengal
    {"code": "SHM", "name": "Shalimar", "hindi": "शालीमार", "city": "Kolkata", "state": "West Bengal", "aliases": ["SHALIMAR", "KOLKATA SHALIMAR", "SHM"]},
    {"code": "SRC", "name": "Santragachi Junction", "hindi": "संत्रागाछी", "city": "Howrah", "state": "West Bengal", "aliases": ["SANTRAGACHI", "SRC"]},
    {"code": "DGR", "name": "Durgapur", "hindi": "दुर्गापुर", "city": "Durgapur", "state": "West Bengal", "aliases": ["DURGAPUR", "DGR"]},
    {"code": "BWN", "name": "Barddhaman Junction", "hindi": "बर्द्धमान", "city": "Bardhaman", "state": "West Bengal", "aliases": ["BARDDHAMAN", "BURDWAN", "BWN"]},
    {"code": "MLDT", "name": "Malda Town", "hindi": "मालदा टाउन", "city": "Malda", "state": "West Bengal", "aliases": ["MALDA", "MLDT"]},

    # Karnataka
    {"code": "MYS", "name": "Mysuru Junction", "hindi": "मैसूरु", "city": "Mysuru", "state": "Karnataka", "aliases": ["MYSURU", "MYSORE", "MYS"]},
    {"code": "UBL", "name": "SSS Hubballi Junction", "hindi": "हुब्बल्ली", "city": "Hubballi", "state": "Karnataka", "aliases": ["HUBBALLI", "HUBLI", "UBL"]},
    {"code": "BGM", "name": "Belagavi", "hindi": "बेलगावी", "city": "Belagavi", "state": "Karnataka", "aliases": ["BELAGAVI", "BELGAUM", "BGM"]},
    {"code": "KLBG", "name": "Kalaburagi Junction (Gulbarga)", "hindi": "कलबुर्गी / गुलबर्गा", "city": "Kalaburagi", "state": "Karnataka", "aliases": ["GULBARGA", "KALABURAGI", "KLBG"]},

    # Tamil Nadu
    {"code": "TBM", "name": "Tambaram", "hindi": "तांबरम", "city": "Chennai", "state": "Tamil Nadu", "aliases": ["TAMBARAM", "CHENNAI TAMBARAM", "TBM"]},
    {"code": "SA", "name": "Salem Junction", "hindi": "सलेम", "city": "Salem", "state": "Tamil Nadu", "aliases": ["SALEM", "SA"]},
    {"code": "ED", "name": "Erode Junction", "hindi": "इरोड", "city": "Erode", "state": "Tamil Nadu", "aliases": ["ERODE", "ED"]},
    {"code": "CAPE", "name": "Kanniyakumari", "hindi": "कन्याकुमारी", "city": "Kanyakumari", "state": "Tamil Nadu", "aliases": ["KANYAKUMARI", "CAPE"]},
    {"code": "RMM", "name": "Rameswaram", "hindi": "रामेश्वरम", "city": "Rameswaram", "state": "Tamil Nadu", "aliases": ["RAMESWARAM", "RMM"]},

    # Kerala
    {"code": "ERN", "name": "Ernakulam Town (North)", "hindi": "एर्नाकुलम टाउन", "city": "Kochi", "state": "Kerala", "aliases": ["ERNAKULAM TOWN", "KOCHI", "ERN"]},
    {"code": "TCR", "name": "Thrissur", "hindi": "त्रिशूर", "city": "Thrissur", "state": "Kerala", "aliases": ["THRISSUR", "TRICHUR", "TCR"]},
    {"code": "CAN", "name": "Kannur", "hindi": "कन्नूर", "city": "Kannur", "state": "Kerala", "aliases": ["KANNUR", "CAN"]},

    # Andhra & Telangana
    {"code": "GNT", "name": "Guntur Junction", "hindi": "गुंटूर", "city": "Guntur", "state": "Andhra Pradesh", "aliases": ["GUNTUR", "GNT"]},
    {"code": "RJY", "name": "Rajahmundry", "hindi": "राजमुंदरी", "city": "Rajahmundry", "state": "Andhra Pradesh", "aliases": ["RAJAHMUNDRY", "RJY"]},
    {"code": "NLR", "name": "Nellore", "hindi": "नेल्लोर", "city": "Nellore", "state": "Andhra Pradesh", "aliases": ["NELLORE", "NLR"]},
    {"code": "GTL", "name": "Guntakal Junction", "hindi": "गुंतकल", "city": "Guntakal", "state": "Andhra Pradesh", "aliases": ["GUNTAKAL", "GTL"]},
    {"code": "WL", "name": "Warangal", "hindi": "वारंगल", "city": "Warangal", "state": "Telangana", "aliases": ["WARANGAL", "WL"]},
    {"code": "KZJ", "name": "Kazipet Junction", "hindi": "काजीपेट", "city": "Warangal", "state": "Telangana", "aliases": ["KAZIPET", "KZJ"]},

    # Odisha & Jharkhand & Chhattisgarh
    {"code": "CTC", "name": "Cuttack Junction", "hindi": "कटक", "city": "Cuttack", "state": "Odisha", "aliases": ["CUTTACK", "CTC"]},
    {"code": "ROU", "name": "Rourkela Junction", "hindi": "राउरकेला", "city": "Rourkela", "state": "Odisha", "aliases": ["ROURKELA", "ROU"]},
    {"code": "HTE", "name": "Hatia", "hindi": "हटिया", "city": "Ranchi", "state": "Jharkhand", "aliases": ["HATIA", "RANCHI HATIA", "HTE"]},
    {"code": "BKSC", "name": "Bokaro Steel City", "hindi": "बोकारो स्टील सिटी", "city": "Bokaro", "state": "Jharkhand", "aliases": ["BOKARO", "BKSC"]},
    {"code": "JSME", "name": "Jasidih Junction (Deoghar)", "hindi": "जसीडीह / देवघर", "city": "Deoghar", "state": "Jharkhand", "aliases": ["JASIDIH", "DEOGHAR", "BAIDYANATH DHAM", "JSME"]},
    {"code": "DURG", "name": "Durg Junction", "hindi": "दुर्ग", "city": "Durg", "state": "Chhattisgarh", "aliases": ["DURG", "BHILAI"]},

    # Uttarakhand & Himachal & J&K
    {"code": "RK", "name": "Roorkee", "hindi": "रुड़की", "city": "Roorkee", "state": "Uttarakhand", "aliases": ["ROORKEE", "RK"]},
    {"code": "KGM", "name": "Kathgodam (Nainital)", "hindi": "काठगोदाम / नैनीताल", "city": "Nainital", "state": "Uttarakhand", "aliases": ["KATHGODAM", "NAINITAL", "KGM"]},
    {"code": "YNRK", "name": "Yog Nagari Rishikesh", "hindi": "योग नगरी ऋषिकेश", "city": "Rishikesh", "state": "Uttarakhand", "aliases": ["RISHIKESH", "YOG NAGARI", "YNRK"]},
    {"code": "SML", "name": "Shimla", "hindi": "शिमला", "city": "Shimla", "state": "Himachal Pradesh", "aliases": ["SHIMLA", "SML"]},
    {"code": "UHP", "name": "Martyr Captain Tushar Mahajan (Udhampur)", "hindi": "उधमपुर", "city": "Udhampur", "state": "Jammu & Kashmir", "aliases": ["UDHAMPUR", "MCTM", "UHP"]},
    {"code": "SINA", "name": "Srinagar Kashmir", "hindi": "श्रीनगर", "city": "Srinagar", "state": "Jammu & Kashmir", "aliases": ["SRINAGAR", "KASHMIR", "SINA"]}
]

for s in additional_stations:
    code = s["code"].upper()
    if code in by_code:
        # Merge aliases
        existing_aliases = set(by_code[code].get("aliases", []))
        existing_aliases.update(s.get("aliases", []))
        by_code[code]["aliases"] = list(existing_aliases)
        if s.get("state"):
            by_code[code]["state"] = s["state"]
        if s.get("city"):
            by_code[code]["city"] = s["city"]
    else:
        by_code[code] = s

final_list = list(by_code.values())
final_list.sort(key=lambda x: (x.get("state", ""), x.get("name", "")))

with open(path, "w", encoding="utf-8") as f:
    json.dump(final_list, f, indent=2, ensure_ascii=False)

print(f"Successfully enriched stations_master.json! Total stations: {len(final_list)}")

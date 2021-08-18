import html
import datetime
import sqlite3
import telebot
import requests
import re
from collections import defaultdict
from geopy.distance import geodesic

class DBEngine():
    def __init__(self, db_name):
        self.db_name = db_name    

    def set_data(self, sql_text, data = ()):
        #try: 
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()
            a = cur.execute(sql_text, data)
            conn.commit()
            res = a.rowcount
        #except Exception as exc:
        #    res = False
        #    raise Exception("cannot write to database " + ''.join(map(str,exc.args)) )
        #finally:
            return res


    def get_data(self, sql_text):
        #try: 
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()
            cur.execute(sql_text)
            return cur.fetchall()
        #except Exception as exc:
        #    raise Exception("cannot read from database " + ''.join(map(str,exc.args)))


class TracksEngine():
    def __init__(self, engine):
        self.db_engine = engine


    def db_init(self):
        sql_text="""CREATE TABLE IF NOT EXISTS tracks(
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            userid TEXT,
            userdata TEXT,
            artist TEXT,
            track TEXT,
            datetime DATE);
        """
        return self.db_engine.set_data(sql_text)


    def db_drop_tracks(self):
        sql_text = "DROP TABLE tracks;"
        return self.db_engine.set_data(sql_text)


    def db_store_track(self, data):
        sql_text = "INSERT INTO tracks VALUES (NULL, ?, ?, ?, ?, ?)"
        return self.db_engine.set_data(sql_text, data)


    def db_get_tracks(self, userid, userdata, numdays):
        wheresql = ''
        usersql = ''
        andsql = ''
        datesql = ''
        
        if userid != 0:
            usersql = " userid='"+str(userid)+"'"
            wheresql = ' where '
        elif userdata != '':
            usersql = " userdata LIKE '%"+userdata+"%'"
            wheresql = ' where '

        if numdays != 0:
            date1 = datetime.datetime.now() - datetime.timedelta(days=numdays)
            date2 = datetime.datetime.now()
            datesql = " datetime>'"+str(date1)+"' and datetime<'"+str(date2)+"'"
            wheresql = ' where '
    
        if usersql != '' and datesql != '':
            andsql = ' and ';

        sql_text = "SELECT * FROM tracks"
        sql_text += wheresql+usersql+andsql+datesql+' order by userdata, datetime;'
        #print(sql_text)    

        return self.db_engine.get_data(sql_text)


    def db_clear_tracks(self, userid, userdata, numdays):
        wheresql = ''
        usersql = ''
        andsql = ''
        datesql = ''

        if userid != 0:
            usersql = " userid='"+str(userid)+"'"
            wheresql = ' where '
        elif userdata != '':
            usersql = " userdata LIKE '%"+userdata+"%'"
            wheresql = ' where '

        if numdays != 0:
            date1 = datetime.datetime.now() - datetime.timedelta(days=numdays)
            datesql = " datetime<'"+str(date1)+"'"
            wheresql = ' where '

        if usersql != '' and datesql != '':
            andsql = ' and ';

        sql_text = "DELETE FROM tracks"+wheresql+usersql+andsql+datesql
        #print(sql_text)    

        return self.db_engine.set_data(sql_text)

class TracksMan():
    def __init__(self, engine):
        self.db_engine = TracksEngine(engine)

    @staticmethod
    def get_on_air():
        site_url = 'http://trance.airtime.pro/api/live-info'
        json_data = requests.get(site_url).json()
        return {
            'Previous':html.unescape(json_data['previous']['name']),
            'Current':html.unescape(json_data['current']['name']),
            'Next':html.unescape(json_data['next']['name']),
        }


    def handle_onair(self, message):
        on_air = self.get_on_air()
        text = 'radiOzora.fm\n';
        for key, value in on_air.items():
            text += key + ': ' + value + '\n'
        return text


    def handle_store(self, message):
        params = message.text.split(' ',1)
        if len(params) > 1:
            if params[1] == 'p':
                on_air = self.get_on_air()['Previous'].split(' - ')
            elif params[1] == 'n':
                on_air = self.get_on_air()['Next'].split(' - ')
            else: 
                on_air = params[1].split(' - ',1)
        else: 
           on_air = self.get_on_air()['Current'].split(' - ')
        #data(userid, userdata, artist, track, datetime)
        
        userdata = str(message.from_user.username or '')+' '+str(message.from_user.first_name or '')+' '+str(message.from_user.last_name or '')
        data = (message.from_user.id, 
                userdata, 
                on_air[0],
                on_air[1],
                datetime.datetime.now()
               )
        self.db_engine.db_store_track(data)
        text = 'stored: ' + on_air[0] + ' - ' +on_air[1]
        return text


    def handle_tracks(self, message):
        userid = message.from_user.id
        username = message.from_user.username
        userdata = ''
        numdays = 0
        fullinfo = False;
        params = message.text.split(' ') 
        for p in params:
            if p == '-f':
                fullinfo = True
            if p[0] == '@':
                userid = 0
                userdata = p.replace('@','')
            if p.isdigit():
                numdays = int(p)
        if userdata == 'all':
            userid = 0
            userdata = ''

        tracks = self.db_engine.db_get_tracks(userid, userdata, numdays)
        usertext = ''
        tracks_text = ''
        for t in tracks:
            usertext = ''
            added_at = datetime.datetime.strptime(t[5], '%Y-%m-%d %H:%M:%S.%f')
            added_at_str = added_at.strftime("%Y.%m.%d %H:%M")
            if userid == 0:
                usertext = t[2]+': '
            if fullinfo:
                tracks_text += added_at_str+' #'+str(t[0])+': '+t[3]+' - '+t[4]+' [added by '+t[2]+']\n'
            else:
                tracks_text += usertext+t[3]+' - '+t[4]+'\n'
        
        if tracks_text != '':
            text = 'Stored tracks:\n'+tracks_text
        else:
            text = 'No stored tracks'
    
        return text


    def handle_clear(self, message):
        userid = message.from_user.id
        username = message.from_user.username
        userdata = ''
        numdays = 0
        params = message.text.split(' ') 
        for p in params:
            if p[0] == '@' and username == 'Wave_zz':
                userid = 0
                userdata = p.replace('@','')
            if p.isdigit():
                numdays = int(p)

        if userdata == 'all' and username == 'Wave_zz':
            userid = 0
            userdata = ''
        
        tracks = self.db_engine.db_clear_tracks(userid, userdata, numdays)

        text = 'removed {} tracks '.format(tracks)
        return text


    def handle_droptracks(self, message):
        if message.from_user.username == 'Wave_zz':
            nrows = self.db_engine.db_drop_tracks()
            text = 'dropped {} table (tracks)'.format(nrows)
        else: 
            text = 'wtf?'
        return text


    def handle_createtracks(self, message):
        if message.from_user.username == 'Wave_zz':
            nrows = self.db_engine.db_init()
            text = 'created {} table (tracks)'.format(nrows)
        else: 
            text = 'wtf?'
        return text


class PlacesEngine():
    def __init__(self, engine):
        self.db_engine = engine
        self.db_init()

    def db_init(self):
        sql_text="""CREATE TABLE IF NOT EXISTS places(
            placeid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            userid TEXT,
            userdata TEXT,
            address TEXT,
            comment TEXT,
            photo BLOB,
            latitude REAL,
            longitude REAL, 
            datetime DATE);
        """
        return self.db_engine.set_data(sql_text)

    def db_drop_places(self):
        sql_text = "DROP TABLE places"
        return self.db_engine.set_data(sql_text)


    def db_store_place(self, data):
        sql_text = "INSERT INTO places VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)"
        #print(sql_text)
        return self.db_engine.set_data(sql_text, data)


    def db_get_places(self, userid, num=10):
        wheresql = ''
        usersql = ''
        limitstr = ''
        if userid != 0:
            usersql = " userid='"+str(userid)+"'"
            wheresql = ' where '

        if num != 0:
            limitstr = " LIMIT "+str(num)

        sql_text = "SELECT * FROM places "
        sql_text += wheresql+usersql+' order by userid, datetime desc'+limitstr
        return self.db_engine.get_data(sql_text)


    def db_get_nearby_places(self, userid, location):
        return []

    def db_clear_places(self, userid):
        sql_text = "DELETE FROM places"
        if userid != 0:
            sql_text += " where userid='"+str(userid)+"'"
        #print(sql_text)    
        return self.db_engine.set_data(sql_text)


class PlacesMan():
    def __init__(self, engine):
        self.locations = {}
        self.db_engine = PlacesEngine(engine)

    @staticmethod
    def is_float(s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    @staticmethod
    def loc2tuple(location):
        #data(userid, username, address, comment, photo, latitude, longitude, datetime)
        #print(location)
        return (location['userid'],
                location['userdata'],
                location['address'],
                location['comment'],
                location['photo'],
                location['latitude'],
                location['longitude'],
                location['datetime']
        )
        

    def get_state(self, message):
        return USER_STATE[message.chat.id]

    def update_state(self, message, state):
        USER_STATE[message.chat.id] = state


    def handle_add(self, message):
        if message.text: 
            text = message.text.split(' ',1)
            command = text[0]
            if command == '/cancel':
                self.update_state(message, NONE)
                return 'adding cancelled'
            data = '' if len(text) == 1 else text[1]
            #print('adding: '+str(self.get_state(message)))  
            
        #else:
            #print('adding photo')  

        if not self.locations.get(message.from_user.id, None):
            userdata = str(message.from_user.username or '')+' '+str(message.from_user.first_name or '')+' '+str(message.from_user.last_name or '')
            self.locations[message.from_user.id]={
               'userid':message.from_user.id,
               'userdata':userdata,
               'address':'',
               'comment':'',
               'photo':None,
               'latitude':0,
               'longitude':0,
               'datetime':0
        }
    
        if self.get_state(message) == NONE:
            #print('adding: none')  
            if data == '':
                self.update_state(message, ADDRESS)
                text = 'Enter address'
            else:
                self.locations[message.from_user.id]['address']=data
                self.locations[message.from_user.id]['datetime']=datetime.datetime.now()
                text = 'added location ' +self.locations[message.from_user.id]['address']
                text += self.locations[message.from_user.id]['comment']
                nrows = self.db_engine.db_store_place(self.loc2tuple(self.locations.pop(message.from_user.id)))
        elif self.get_state(message) == ADDRESS:
            #print('adding: address')  
            if message.text:            
                self.locations[message.from_user.id]['address']=message.text
                self.update_state(message, COMMENT)
                text = 'Enter comment'
            else:
                text = 'Enter address'

        elif self.get_state(message) == COMMENT:
            #print('adding: comment')  
            if message.text:            
                self.locations[message.from_user.id]['comment']=message.text
                self.update_state(message, PHOTO)
                text = 'Add photo'
            else:
                text = 'Enter comment'
        
        elif self.get_state(message) == PHOTO:
            if message.photo:
                #print('adding: photo')  
                #print(message.photo)
                #print(message.photo[0])
                #print(message.photo[1])
                file_info = bot.get_file(message.photo[len(message.photo)-1].file_id)
                photo = bot.download_file(file_info.file_path)
                self.locations[message.from_user.id]['photo']=photo            
                self.update_state(message, GEOLOC)
                text = 'Add geolocation (attach or enter [latitude,longitude])'
            else: 
                text = 'Add photo'
        elif self.get_state(message) == GEOLOC:
            #print('adding: geoloc')  
            #print(message.location)  
            self.locations[message.from_user.id]['latitude']=-1
            self.locations[message.from_user.id]['longitude']=-1
            if message.location:
                self.locations[message.from_user.id]['latitude']=message.location.latitude
                self.locations[message.from_user.id]['longitude']=message.location.longitude    
            else:
                try:
                    m = message.text.replace('[','').replace(']','').split(',') 
                    self.locations[message.from_user.id]['latitude']= float(m[0]) 
                    self.locations[message.from_user.id]['longitude'] = float(m[1]) 
                except:
                    pass

            if self.locations[message.from_user.id]['latitude']<0 or self.locations[message.from_user.id]['longitude']<0:
                return 'Add geolocation (attach or enter [latitude,longitude])'
            else:
                self.update_state(message, CONFIRM)
                text = 'address: '+self.locations[message.from_user.id]['address']+'\n'
                text += 'comment: '+self.locations[message.from_user.id]['comment']+'\n'
                #text += 'photo: '+self.locations[message.from_user.id]['photo']+'\n'
                text += 'location: '+str(self.locations[message.from_user.id]['latitude'])+', '
                text += str(self.locations[message.from_user.id]['longitude'])+'\n'
                #print('sending photo')  
                bot.send_photo(message.chat.id, self.locations[message.from_user.id]['photo'], caption = text)
                #print('end sending photo')  
                return 'Saving? (yes/no)'
                             
        elif self.get_state(message) == CONFIRM:
            if message.text.lower() == 'yes':
                self.update_state(message, NONE)
                self.locations[message.from_user.id]['datetime']=datetime.datetime.now()
                text = 'added location ' +self.locations[message.from_user.id]['address']
                text += ' '+self.locations[message.from_user.id]['comment']
                nrows = self.db_engine.db_store_place(self.loc2tuple(self.locations.pop(message.from_user.id)))
            if message.text.lower() == 'no':
                self.update_state(message, NONE)
                text = 'cancelled location ' +self.locations[message.from_user.id]['address']
                text += ' '+self.locations[message.from_user.id]['comment']
                self.locations.pop(message.from_user.id)
        return text


    def handle_list(self, message):
        userid = message.from_user.id
        #print('list')
        row_limit = 0 if message.location else 10
        places = self.db_engine.db_get_places(userid, row_limit)
        text = ''
        for p in places:
            dest = 0
            if message.location:
                my_loc = (message.location.latitude,message.location.longitude)
                p_loc =  (p[6],p[7])
                dest = geodesic(my_loc,p_loc).kilometers * 1000
                #print(dest)
            if dest <= 500:
                added_at =  datetime.datetime.strptime(p[8], '%Y-%m-%d %H:%M:%S.%f')
                added_at_str = added_at.strftime("%d.%m.%Y %H:%M")
                text = 'added on '+added_at_str+'\n'
                text += 'address: '+p[3]+'\n'
                if p[4] != '':
                    text += 'comment: '+p[4]+'\n'
                text += 'location: ('+str(p[6])+', '+str(p[7])+') \n'
                if p[5]:
                    bot.send_photo(message.chat.id, p[5], caption = text)
                else:
                    bot.send_message(message.chat.id, text = text)

        return 'No places added' if text == '' else ''


    def handle_reset(self, message):
        userid = message.from_user.id
 
        if message.from_user.username == 'Wave_zz':
            params = message.text.split(' ',1) 
            if len(params) >1:
                if params[1].isdigit():
                    userid = int(params[1])
                elif params[1] == 'all':                  
                    userid = 0  

        nrows = self.db_engine.db_clear_places(userid)

        text = 'Removed {} places'.format(nrows)
        return text


    def handle_dropplaces(self, message):
        if message.from_user.username == 'Wave_zz':
            nrows = self.db_engine.db_drop_places()
            text = 'dropped {} table (places)'.format(nrows)
        else: 
            text = 'wtf?'
        return text


    def handle_createplaces(self, message):
        if message.from_user.username == 'Wave_zz':
            nrows = self.db_engine.db_init()
            text = 'created {} table (places)'.format(nrows)
        else: 
            text = 'wtf?'
        return text


token = '1934992652:AAGRBqptF7puyZSETtt139aKBCwVjbEJHUg'
bot = telebot.TeleBot(token)
db_engine = DBEngine('wavebot.db')
tracks_man = TracksMan(db_engine) 
places_man = PlacesMan(db_engine) 
USER_STATE = defaultdict(lambda: NONE)
NONE, ADDRESS, COMMENT, PHOTO, GEOLOC, CONFIRM = range(6)


@bot.message_handler(commands = ['start'])
def handle_start(message):
    text = "Welcome, my little adventurer!"+"\n\n"

    text += "Location commands:"+"\n"
    text += "/add adds location"+"\n"
    text += "/cancel cancels adding location"+"\n"
    text += "/list shows added locations"+"\n"
    text += "/reset removes added locations\n\n"
    text += "Also you get added locations within 500m by sending me your current location"
        
    bot.send_message(message.chat.id, text = text)


@bot.message_handler(commands = ['onair','store','tracks','clear','droptracks','createtracks'])
def handle_radio_commands(message):
    text = message.text.split(' ',1)
    command = text[0]
    try: 
        if command == '/onair':
            text = tracks_man.handle_onair(message)
        elif command == '/store':
            text = tracks_man.handle_store(message)
        elif command == '/tracks':
            text = tracks_man.handle_tracks(message)
        elif command == '/clear':
            text = tracks_man.handle_clear(message)
        elif command == '/droptracks':
            text = tracks_man.handle_droptracks(message)
        elif command == '/createtracks':
            text = tracks_man.handle_createtracks(message)
    except Exception as exc:
        text = 'error: '+ ''.join(map(str,exc.args))
    finally:
        bot.send_message(message.chat.id, text = text)


@bot.message_handler(commands = ['add','cancel','list','reset','dropplaces','createplaces'])
def handle_commands(message):
    text = message.text.split(' ',1)
    command = text[0]
    try: 
        if command == '/add':
            text = places_man.handle_add(message)
        if command == '/cancel':
            text = places_man.handle_add(message)
        elif command == '/list':
            text = places_man.handle_list(message)
        elif command == '/reset':
            text = places_man.handle_reset(message)
        elif command == '/dropplaces':
            text = places_man.handle_dropplaces(message)
        elif command == '/createplaces':
            text = places_man.handle_createplaces(message)
    except Exception as exc:
        text = 'error: '+ ''.join(map(str,exc.args))
    finally:
        if text != '':
            bot.send_message(message.chat.id, text = text)

    

@bot.message_handler(content_types=['photo'])
def handle_message(message):

    #print('image')

    if places_man.get_state(message) != NONE:
        text = places_man.handle_add(message)
        bot.send_message(message.chat.id, text = text)

@bot.message_handler(content_types=['location'])
def handle_message(message):

    #print('location')

    if places_man.get_state(message) != NONE:
        text = places_man.handle_add(message)
        bot.send_message(message.chat.id, text = text)
    else: 
        text = places_man.handle_list(message)
        if text != '':
            bot.send_message(message.chat.id, text = text)

@bot.message_handler(content_types=['text'])
def handle_message(message):

    #print('message')

    if places_man.get_state(message) != NONE:
        #print('message: not none')
        text = places_man.handle_add(message)
        bot.send_message(message.chat.id, text = text)
        return

    if 'radio' in message.text.lower():
        text = "radio commands:"+"\n\n"
        text += "/onair shows what's playing now"+"\n"
        text += "/tracks [@user][@all] [days] shows stored tracks"+"\n"
        text += "     user - of certain user, all - all, w/o - mine"+"\n"
        text += "     days - number of last days to show, w/o - all time"+"\n"
        text += "/store [p][n][artist - track] store track info "+"\n"
        text += "     p - prevous, n - next, w/o - current "+"\n"
        text += "     artist, track - to store text data "+"\n"
        text += "/clear [days] removes tracks from list "+"\n"
        text += "     days - number of last days to keep, w/o - all time "+"\n"
    elif 'hello' in message.text.lower() or 'hi' in message.text.lower():
        text = 'Yo'
    else:
        text = 'huh?'
    bot.send_message(message.chat.id, text = text)


def main():
    bot.polling()

if __name__ == '__main__':
    main()
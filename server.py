# server.py
import socket
import threading
import json
import time
from datetime import datetime
import re
import random

kayitli_kullanicilar = {}  # {'kullanici': 'sifre'}
online_kullanicilar = {}  # {'kullanici': soket}
arkadas_listeleri = {}  # {'kullanici': ['arkadas1', ...]}
bekleyen_istekler = {}

sohbet_gecmisi = {}  # {'kullanici1-kullanici2': [mesajlar]}
odalar = {"Genel": [], "Yazilim": [], "Oyun": []}

son_gorulme_zamanlari = {}# yapi: {'kullanici_adi': {'arkadas_veya_oda_adi': '20:30:00'}}
spam_listeleri = {}  # {'kullanici': ['kelime1', 'kelime2']}


def kanal_olustur(u1, u2):
    return "-".join(sorted([u1, u2]))


def baglanti_kontrol(client_soket, client_adres):
    kullanici_adi = None
    dogrulama_cevap = None

    while True:
        try:
            gelen_paket = client_soket.recv(4096).decode('utf-8')
            if not gelen_paket: break

            veri_sozlugu = json.loads(gelen_paket)
            islem = veri_sozlugu.get("tip")
            zaman = datetime.now().strftime("%H:%M:%S")

            if islem == "ping":
                client_soket.send(json.dumps({"tip": "gecikme_yaniti"}).encode('utf-8'))
                continue

            # kayit ve giris islemleri

            if islem == "kayit":
                isim, sifre = veri_sozlugu.get("isim"), veri_sozlugu.get("sifre")

                if isim in kayitli_kullanicilar:
                    client_soket.send(json.dumps({"tip": "hata", "mesaj": "hata olustu: Bu isim başka bir kullanici tarafindan kullaniliyor!"}).encode('utf-8'))

                else:
                    kayitli_kullanicilar[isim] = sifre
                    arkadas_listeleri[isim], bekleyen_istekler[isim] = [], []
                    client_soket.send(json.dumps({"tip": "basari", "mesaj": "Kayıt başarılı sekilde tamamlandı."}).encode('utf-8'))

            elif islem == "giris":
                isim, sifre = veri_sozlugu.get("isim"), veri_sozlugu.get("sifre")

                if isim not in kayitli_kullanicilar:
                    client_soket.send(json.dumps({"tip": "hata", "mesaj": "hata olustu: Böyle bir kullanıcıyı sistemde bulamadık.!"}).encode('utf-8'))

                elif kayitli_kullanicilar[isim] != sifre:
                    client_soket.send(json.dumps({"tip": "hata", "mesaj": "hata olustu: Yanlış şifre girdin, tekrar dene.!"}).encode('utf-8'))

                else:
                    s1, s2 = random.randint(1, 10), random.randint(1, 10)
                    dogrulama_cevap = s1 + s2
                    client_soket.send(json.dumps({"tip": "guvenlik_testi","soru": f"Güvenlik Doğrulaması: {s1} + {s2} = ?","aday_kullanici": isim}).encode('utf-8'))

            elif islem == "dogrulama_yap":
                kullanici_yaniti = veri_sozlugu.get("cevap")
                isim = veri_sozlugu.get("isim")

                if str(kullanici_yaniti) == str(dogrulama_cevap):
                    kullanici_adi = isim
                    online_kullanicilar[kullanici_adi] = client_soket
                    client_soket.send(json.dumps({"tip": "giris_basarili", "isim": kullanici_adi}).encode('utf-8'))

                    for arkadas in arkadas_listeleri.get(kullanici_adi, []):
                        if arkadas in online_kullanicilar:
                            online_kullanicilar[arkadas].send(json.dumps({"tip": "durum_guncelleme", "gonderen": kullanici_adi, "durum": "çevrimiçi"}).encode('utf-8'))

                else:
                    client_soket.send(json.dumps({"tip": "hata", "mesaj": "hata olustu: Girdiğiniz doğrulama kodu yanlış!"}).encode('utf-8'))

            # arkadaslik sistemi

            elif islem == "arkadas_istegi_at" and kullanici_adi:
                istek_atilan = veri_sozlugu.get("hedef")

                if istek_atilan not in kayitli_kullanicilar:
                    client_soket.send(json.dumps({"tip": "hata", "mesaj": "hata olustu: Kullanıcı sistemde kayıtlı değil!"}).encode('utf-8'))

                elif istek_atilan == kullanici_adi:
                    client_soket.send(json.dumps({"tip": "hata", "mesaj": "hata olustu: Kendinize istek atamazsınız!"}).encode('utf-8'))

                else:
                    bekleyen_istekler[istek_atilan].append(kullanici_adi)
                    if istek_atilan in online_kullanicilar:
                        online_kullanicilar[istek_atilan].send(json.dumps({"tip": "sistem_mesaji", "mesaj": f"{kullanici_adi} size istek gönderdi!"}).encode('utf-8'))

                    client_soket.send(json.dumps({"tip": "basari", "mesaj": "İstek iletildi."}).encode('utf-8'))

            elif islem == "istek_onayla" and kullanici_adi:
                onaylanan_kisi = veri_sozlugu.get("isim")

                if onaylanan_kisi in bekleyen_istekler[kullanici_adi]:
                    arkadas_listeleri[kullanici_adi].append(onaylanan_kisi)
                    arkadas_listeleri[onaylanan_kisi].append(kullanici_adi)
                    bekleyen_istekler[kullanici_adi].remove(onaylanan_kisi)

                    client_soket.send(json.dumps({"tip": "sistem_mesaji", "mesaj": f"{onaylanan_kisi} ile arkadaş oldunuz!"}).encode('utf-8'))

                    if onaylanan_kisi in online_kullanicilar:
                        online_kullanicilar[onaylanan_kisi].send(json.dumps({"tip": "sistem_mesaji", "mesaj": f"{kullanici_adi} onayladı!"}).encode('utf-8'))

                else:
                    client_soket.send(json.dumps({"tip": "hata", "mesaj": "hata olustu: Aradığınız istek bulunamadı!"}).encode('utf-8'))

            # sohbet ve mesaj islemleri

            elif islem == "sohbet_yukle" and kullanici_adi:
                arkadas = veri_sozlugu.get("arkadas")

                if arkadas in arkadas_listeleri.get(kullanici_adi, []):
                    sohbet_id = kanal_olustur(kullanici_adi, arkadas)
                    tum_mesajlar = sohbet_gecmisi.get(sohbet_id, [])

                    # özet mantigi
                    gorulme_verileri = son_gorulme_zamanlari.get(kullanici_adi, {})
                    son_okuma = gorulme_verileri.get(arkadas, "00:00:00")
                    okunmamis_mesajlar = [msg for msg in tum_mesajlar if msg['tarih'] > son_okuma]

                    if len(okunmamis_mesajlar) >= 10:
                        client_soket.send(json.dumps({"tip": "ozet_teklifi","miktar": len(okunmamis_mesajlar),"arkadas": arkadas}).encode('utf-8'))

                    if kullanici_adi not in son_gorulme_zamanlari: son_gorulme_zamanlari[kullanici_adi] = {}
                    son_gorulme_zamanlari[kullanici_adi][arkadas] = datetime.now().strftime("%H:%M:%S")

                    maskelenmis_gecmis = []
                    for msg in tum_mesajlar:
                        gecici_mesaj = msg.copy()

                        if gecici_mesaj.get("spam_mi") == True and gecici_mesaj["gonderen"] != kullanici_adi:
                            gecici_mesaj["mesaj"] = "--- SPAM MESAJI (Görmek için 'Spam Aç' (menü->9) kullanın) ---"

                        maskelenmis_gecmis.append(gecici_mesaj)

                    client_soket.send(json.dumps({"tip": "sohbet_verisi", "mesajlar": maskelenmis_gecmis}).encode('utf-8'))

            elif islem == "ozel_mesaj" and kullanici_adi:
                alici = veri_sozlugu.get("alici")
                mesaj_metni = veri_sozlugu.get("mesaj")

                if alici in arkadas_listeleri.get(kullanici_adi, []):
                    mesaj_id = f"{int(time.time()) % 10000}-{random.randint(100, 999)}"
                    yasakli_kelimeler = spam_listeleri.get(alici, [])
                    spam_mi = any(kelime.lower() in mesaj_metni.lower() for kelime in yasakli_kelimeler)

                    olusturulan_mesaj = {
                        "id": mesaj_id,
                        "gonderen": kullanici_adi,
                        "mesaj": mesaj_metni,
                        "tarih": zaman,
                        "begenildi": False,
                        "spam_mi": spam_mi
                    }

                    sohbet_id = kanal_olustur(kullanici_adi, alici)
                    if sohbet_id not in sohbet_gecmisi: sohbet_gecmisi[sohbet_id] = []
                    sohbet_gecmisi[sohbet_id].append(olusturulan_mesaj)

                    if alici in online_kullanicilar:
                        gecici_mesaj = olusturulan_mesaj.copy()

                        if spam_mi:
                            gecici_mesaj["mesaj"] = f"--- {kullanici_adi} tarafından gönderilen spam mesajı! ---"

                        online_kullanicilar[alici].send(json.dumps({
                            "tip": "yeni_mesaj",
                            "veri": gecici_mesaj,
                            "sohbet_arkadasi": kullanici_adi,
                            "spam_uyarisi": spam_mi
                        }).encode('utf-8'))

                else:
                    client_soket.send(
                        json.dumps({"tip": "hata", "mesaj": "hata olustu: Sadece arkadaşlara mesaj atabilirsiniz!"}).encode('utf-8'))

            elif islem in ["mesaj_sil", "mesaj_duzenle", "mesaj_begen"] and kullanici_adi:
                arkadas, mesaj_id = veri_sozlugu.get("arkadas"), veri_sozlugu.get("mesaj_id")
                sohbet_id = kanal_olustur(kullanici_adi, arkadas)

                if sohbet_id in sohbet_gecmisi:
                    for msg in sohbet_gecmisi[sohbet_id]:
                        if msg["id"] == mesaj_id:
                            if islem == "mesaj_sil":
                                msg["mesaj"] = "--- Bu mesaj silindi ---"
                            elif islem == "mesaj_duzenle":
                                msg["mesaj"] = veri_sozlugu.get("yeni") + " (Düzenlendi)"
                            elif islem == "mesaj_begen":
                                msg["begenildi"] = not msg.get("begenildi", False)

                            if arkadas in online_kullanicilar:
                                online_kullanicilar[arkadas].send(json.dumps(
                                    {"tip": "mesaj_guncelleme", "id": mesaj_id, "yeni": msg["mesaj"],
                                     "tip_ek": islem}).encode('utf-8'))
                            break

            # oda sistemi

            elif islem == "oda_listele_genel" and kullanici_adi:
                client_soket.send(json.dumps({"tip": "sistem_mesaji", "mesaj": f"Odalar: {', '.join(odalar.keys())}"}).encode('utf-8'))

            elif islem == "oda_katil" and kullanici_adi:
                oda_liste = veri_sozlugu.get("oda")

                if oda_liste in odalar:
                    if kullanici_adi not in odalar[oda_liste]: odalar[oda_liste].append(kullanici_adi)

                    gorulme_verileri = son_gorulme_zamanlari.get(kullanici_adi, {})
                    son_okuma = gorulme_verileri.get(oda_liste, "00:00:00")
                    oda_gecmisi = sohbet_gecmisi.get(oda_liste, [])
                    okunmamis_mesajlar = [msg for msg in oda_gecmisi if msg['tarih'] > son_okuma]

                    if len(okunmamis_mesajlar) >= 10:
                        client_soket.send(json.dumps({"tip": "ozet_teklifi", "miktar": len(okunmamis_mesajlar), "oda": oda_liste}).encode('utf-8'))

                    if kullanici_adi not in son_gorulme_zamanlari: son_gorulme_zamanlari[kullanici_adi] = {}
                    son_gorulme_zamanlari[kullanici_adi][oda_liste] = datetime.now().strftime("%H:%M:%S")
                    client_soket.send(json.dumps({"tip": "basari", "mesaj": f"{oda_liste} odasına başarılı şekilde girildi."}).encode('utf-8'))

                else:
                    client_soket.send(json.dumps({"tip": "hata", "mesaj": "hata olustu: Geçersiz oda adı!"}).encode('utf-8'))

            elif islem == "oda_mesaji" and kullanici_adi:
                oda_liste = veri_sozlugu.get("oda")
                if oda_liste in odalar and kullanici_adi in odalar[oda_liste]:
                    if oda_liste not in sohbet_gecmisi: sohbet_gecmisi[oda_liste] = []
                    sohbet_gecmisi[oda_liste].append({"gonderen": kullanici_adi, "mesaj": veri_sozlugu.get("mesaj"), "tarih": zaman})

                    for aktif_uye in odalar[oda_liste]:
                        if aktif_uye != kullanici_adi:
                            online_kullanicilar[aktif_uye].send(json.dumps({"tip": "oda_mesaji", "oda": oda_liste, "gonderen": kullanici_adi,"mesaj": veri_sozlugu.get("mesaj"), "tarih": zaman}).encode('utf-8'))
                else:
                    client_soket.send(
                        json.dumps({"tip": "hata", "mesaj": "hata olustu: Bu odaya üye değilsiniz!"}).encode('utf-8'))

            elif islem == "oda_uyeleri" and kullanici_adi:
                oda_liste = veri_sozlugu.get("oda")
                if oda_liste in odalar and kullanici_adi in odalar[oda_liste]:
                    client_soket.send(json.dumps({"tip": "sistem_mesaji", "mesaj": f" Oda üyeleri: {', '.join(odalar[oda_liste])}"}).encode('utf-8'))

            # spam ve özet islemleri

            elif islem == "spam_kelime_ekle" and kullanici_adi:
                kelime = veri_sozlugu.get("kelime").lower()
                if kullanici_adi not in spam_listeleri: spam_listeleri[kullanici_adi] = []

                if kelime not in spam_listeleri[kullanici_adi]:
                    spam_listeleri[kullanici_adi].append(kelime)
                    client_soket.send(json.dumps({"tip": "basari", "mesaj": f"'{kelime}' listeye eklendi."}).encode('utf-8'))

            elif islem == "spam_ac" and kullanici_adi:
                arkadas, mesaj_id = veri_sozlugu.get("arkadas"), veri_sozlugu.get("mesaj_id")
                sohbet_id = kanal_olustur(kullanici_adi, arkadas)
                bulunduMu = False

                for msg in sohbet_gecmisi.get(sohbet_id, []):
                    if msg["id"] == mesaj_id:
                        client_soket.send(json.dumps({"tip": "sistem_mesaji", "mesaj": f"Gizli: {msg['mesaj']}"}).encode('utf-8'))
                        bulunduMu = True;
                        break
                if not bulunduMu: client_soket.send(json.dumps({"tip": "hata", "mesaj": "Mesaj bulunamadı!"}).encode('utf-8'))

            elif islem == "ozet_uret" and kullanici_adi:
                arkadas = veri_sozlugu.get("arkadas")
                oda_liste = veri_sozlugu.get("oda")
                sohbet_id = oda_liste if oda_liste else kanal_olustur(kullanici_adi, arkadas)
                gecmis = sohbet_gecmisi.get(sohbet_id, [])

                son_mesajlar = [str(m["mesaj"]) for m in gecmis[-20:]]
                tum_metin = " ".join(son_mesajlar).lower()

                # noktalama isaretlerini temizlemek icin regex kullandim  *hazir kalip
                temiz_metin = re.sub(r'[^\w\s]', '', tum_metin)
                kelimeler = temiz_metin.split()

                cikarilacak_kelimeler = ["ve", "bir", "bu", "da", "de", "mi", "ama", "için", "çok", "en", "şey",
                                         "zaten", "tamam", "yok", "evet", "hayır", "kanka", "abi", "ya"]

                analiz_listesi = [k for k in kelimeler if k not in cikarilacak_kelimeler and len(k) > 3]

                kelime_sayac = {}
                for k in analiz_listesi: kelime_sayac[k] = kelime_sayac.get(k, 0) + 1

                sirali = sorted(kelime_sayac.items(), key=lambda x: x[1], reverse=True)[:5]
                ozet_kelimeler = [f"{item[0]} ({item[1]} kez)" for item in sirali]

                sonuc = f"💡 Özet: Bu sohbette en çok bu konular üzerinde durulmuş: {', '.join(ozet_kelimeler)}" if ozet_kelimeler else "💡 Özet: Analiz yapılamadı."
                client_soket.send(json.dumps({"tip": "sistem_mesaji", "mesaj": sonuc}).encode('utf-8'))

            elif islem == "durum_guncelleme" and kullanici_adi:
                alici = veri_sozlugu.get("alici")

                if alici in arkadas_listeleri.get(kullanici_adi, []) and alici in online_kullanicilar:
                    online_kullanicilar[alici].send(json.dumps(veri_sozlugu).encode('utf-8'))

        except:
            break

    if kullanici_adi:
        if kullanici_adi in online_kullanicilar: del online_kullanicilar[kullanici_adi]

        for oda_liste_obj in odalar.values():
            if kullanici_adi in oda_liste_obj: oda_liste_obj.remove(kullanici_adi)

        cevrimdisi_bildirimi = {"tip": "durum_guncelleme", "gonderen": kullanici_adi, "durum": "çevrimdışı"}
        for arkadas_eleman in arkadas_listeleri.get(kullanici_adi, []):

            if arkadas_eleman in online_kullanicilar:
                try:
                    online_kullanicilar[arkadas_eleman].send(json.dumps(cevrimdisi_bildirimi).encode('utf-8'))
                except:
                    pass

    client_soket.close()


# server baslatma
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # 'Address already in use' hatasını çözmek için ekledim
server.bind(('0.0.0.0', 6060))
server.listen()

print("Sunucu başlatıldı.")

while True:
    client_soket, client_adres = server.accept()
    threading.Thread(target=baglanti_kontrol, args=(client_soket, client_adres)).start()



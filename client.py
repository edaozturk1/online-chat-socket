# client.py
import socket
import threading
import json
import time

gecikme_suresi = "ölçülüyor..."
baslangic_zamani = 0

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ozet_bilgi = None
client.connect(('127.0.0.1', 6060))

giris_onay = False
dogrulama = False
dogrulanan_kisi = ""

# sunucudan gelen paketleri burada ayikliyoruz
def mesajlari_al():
    global giris_onay, gecikme_suresi

    while True:
        try:
            gelen_paket = client.recv(4096).decode('utf-8')
            if not gelen_paket: break

            paket_icerik = json.loads(gelen_paket)

            if paket_icerik["tip"] == "gecikme_yaniti":
                bitis_zamani = time.perf_counter()
                gecikme_degeri = (bitis_zamani - baslangic_zamani) * 1000
                gecikme_suresi = f"{gecikme_degeri:.2f} ms"

            elif paket_icerik["tip"] == "guvenlik_testi":
                print(f"\n[GÜVENLİK SİSTEMİ]: {paket_icerik['soru']}")
                global dogrulama, dogrulanan_kisi
                dogrulanan_kisi = paket_icerik["aday_kullanici"]
                dogrulama = True

            if paket_icerik["tip"] == "giris_basarili":
                giris_onay = True
                print("\n[GİRİŞ]: Giriş Başarılı!")

            elif paket_icerik["tip"] == "hata":
                print(f"\n[HATA]: {paket_icerik['mesaj']}")

            elif paket_icerik["tip"] == "basari":
                print(f"\n[BAŞARILI]: {paket_icerik['mesaj']}")

            elif paket_icerik["tip"] == "sistem_mesaji":
                print(f"\n[BİLDİRİM]: {paket_icerik['mesaj']}")

            elif paket_icerik["tip"] == "yeni_mesaj":
                mesaj_etiketi = "[SPAM BİLDİRİMİ]" if paket_icerik.get("spam_uyarisi") else f"[{paket_icerik['veri']['tarih']}]"

                print(f"\n{mesaj_etiketi} {paket_icerik['sohbet_arkadasi']}: {paket_icerik['veri']['mesaj']} (ID: {paket_icerik['veri']['id']})")

            elif paket_icerik["tip"] == "sohbet_verisi":
                print(f"\n--- SOHBET GEÇMİŞİ ---\n{json.dumps(paket_icerik['mesajlar'], indent=2)}")

            elif paket_icerik["tip"] == "oda_mesaji":
                print(f"\n[{paket_icerik['tarih']}] [{paket_icerik['oda']}] {paket_icerik['gonderen']}: {paket_icerik['mesaj']}")

            elif paket_icerik["tip"] == "ozet_teklifi":

                global ozet_bilgi
                sohbet_konumu = paket_icerik.get("oda") if paket_icerik.get("oda") else paket_icerik.get("arkadas")
                ozet_bilgi = {"tip": "oda" if paket_icerik.get("oda") else "arkadas", "isim": sohbet_konumu}

                print(f"\n" + "=" * 40)
                print(f"[BİLGİ]: {sohbet_konumu} sohbetinde {paket_icerik['miktar']} okunmamış mesajınız var!")
                print(f"Hızlı özeti görmek için menü kısmından '0' tuşuna basın.")
                print("=" * 40 + "\n")

            elif paket_icerik["tip"] == "durum_guncelleme":
                print(f"\n[DURUM]: {paket_icerik['gonderen']} {paket_icerik['durum']}")

        except:
            break


def hiz_takibi():
    global baslangic_zamani

    while True:
        if giris_onay:

            try:
                baslangic_zamani = time.perf_counter()
                client.send(json.dumps({"tip": "ping"}).encode('utf-8'))
            except:
                break

        time.sleep(3)


threading.Thread(target=mesajlari_al, daemon=True).start()
threading.Thread(target=hiz_takibi, daemon=True).start()

# giris dongusu
while not giris_onay:
    if not dogrulama:
        print("\n1: Kayıt Ol | 2: Giriş Yap | q: Çıkış Yap ")
        islem_secimi = input("Seçiminiz: ")

        if islem_secimi == "q":
            exit()

        ad = input("Adınız: ")
        sifre = input("Şifre: ")
        client.send(json.dumps({"tip": "kayit" if islem_secimi == "1" else "giris", "isim": ad, "sifre": sifre}).encode('utf-8'))
        time.sleep(1)

    else:
        kullanici_yaniti = input("Cevabınız: ")
        client.send(json.dumps({"tip": "dogrulama_yap", "cevap": kullanici_yaniti, "isim": dogrulanan_kisi}).encode('utf-8'))
        dogrulama = False
        time.sleep(1)

# Ana menü - q basana kadar uygulama kapanmaz
while True:
    print(f"\n--- {ad.upper()} MENÜ | gecikme suresi: {gecikme_suresi} ---")
    print("1: Arkadaşlık İsteği At | 2: Arkadaşlık İsteklerini Onayla")
    print("3: Sohbet İslemleri")
    print("4: Odaları Listele | 5: Odaya Katıl | 6: Odaya Yaz | 7: Oda Üyelerini Listele")
    print("8: Spam Kelime Ekle | 9: Spam Mesajı Aç | 0: Özet Göster")
    print("q: Çıkış")

    menu_secim = input("Seçim: ")

    if menu_secim == "1":
        client.send(json.dumps({"tip": "arkadas_istegi_at", "hedef": input("Kullanıcı Adı: ")}).encode('utf-8'))

    elif menu_secim == "2":
        client.send(json.dumps({"tip": "istek_onayla", "isim": input("Kişi Adı: ")}).encode('utf-8'))

    elif menu_secim == "3":
        sohbet_arkadasi = input("Kiminle sohbet etmek istiyorsunuz: ")
        client.send(json.dumps({"tip": "sohbet_yukle", "arkadas": sohbet_arkadasi}).encode('utf-8'))
        islem = input("[M]esaj | [S]il | [D]üzenle | [B]eğen: ").upper()

        if islem == "M":
            client.send(json.dumps({"tip": "durum_guncelleme", "alici": sohbet_arkadasi, "gonderen": ad, "durum": "yazıyor..."}).encode('utf-8'))
            client.send(json.dumps({"tip": "ozel_mesaj", "alici": sohbet_arkadasi, "mesaj": input("Mesaj: ")}).encode('utf-8'))

        elif islem == "S":
            client.send(json.dumps({"tip": "mesaj_sil", "arkadas": sohbet_arkadasi, "mesaj_id": input("Silinecek mesaj ID: ")}).encode('utf-8'))

        elif islem == "D":
            client.send(json.dumps({"tip": "mesaj_duzenle", "arkadas": sohbet_arkadasi, "mesaj_id": input("ID: "),"yeni": input("Yeni Mesaj: ")}).encode('utf-8'))

        elif islem == "B":
            client.send(json.dumps({"tip": "mesaj_begen", "arkadas": sohbet_arkadasi, "mesaj_id": input("ID: ")}).encode('utf-8'))

    elif menu_secim == "0":
        if ozet_bilgi:
            ozet_talebi = {"tip": "ozet_uret"}

            if ozet_bilgi["tip"] == "oda":
                ozet_talebi["oda"] = ozet_bilgi["isim"]

            else:
                ozet_talebi["arkadas"] = ozet_bilgi["isim"]

            client.send(json.dumps(ozet_talebi).encode('utf-8'))
            ozet_bilgi = None

        else:
            print("\n[!] Özetlenecek birikmiş mesajınız bulunamadi.")

    elif menu_secim == "4":
        client.send(json.dumps({"tip": "oda_listele_genel"}).encode('utf-8'))

    elif menu_secim == "5":
        client.send(json.dumps({"tip": "oda_katil", "oda": input("Oda Adı: ")}).encode('utf-8'))

    elif menu_secim == "6":
        client.send(json.dumps({"tip": "oda_mesaji", "oda": input("Oda: "), "mesaj": input("Mesaj: ")}).encode('utf-8'))

    elif menu_secim == "7":
        client.send(json.dumps({"tip": "oda_uyeleri", "oda": input("Oda: ")}).encode('utf-8'))

    elif menu_secim == "8":
        client.send(json.dumps({"tip": "spam_kelime_ekle", "kelime": input("Spam kelime: ")}).encode('utf-8'))

    elif menu_secim == "9":
        sohbet_arkadasi = input("Hangi arkadaş sohbetinde: ")
        mesaj_id = input("Mesajın ID: ")
        client.send(json.dumps({"tip": "spam_ac", "arkadas": sohbet_arkadasi, "mesaj_id": mesaj_id}).encode('utf-8'))

    elif menu_secim == "q":
        break

client.close()







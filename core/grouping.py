def grupla(kararlar, dava_basina):
    if dava_basina < 1:
        dava_basina = 1
    return [kararlar[i:i + dava_basina] for i in range(0, len(kararlar), dava_basina)]

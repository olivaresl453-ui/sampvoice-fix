import pathlib, sys

ROOT = pathlib.Path("src/server")

def sub(name, old, new):
    p = ROOT / name
    t = p.read_text(encoding="utf-8")
    if new in t:
        print("[ya parcheado]", name); return
    if old not in t:
        sys.exit("[ERROR] no se encontro el bloque en " + name)
    p.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("[parcheado]", name)

OLD_ADD = '''        PlayerStore::playerMutex[playerId].lock();
        const auto pOldPlayerInfo = PlayerStore::playerInfo[playerId].exchange(pPlayerInfo, std::memory_order_acq_rel);
        PlayerStore::playerMutex[playerId].unlock();

        if (pOldPlayerInfo != nullptr)
        {
            for (const auto stream : pOldPlayerInfo->listenerStreams)
                stream->DetachListener(playerId);

            for (const auto stream : pOldPlayerInfo->speakerStreams)
                stream->DetachSpeaker(playerId);

            delete pOldPlayerInfo;
        }'''

NEW_ADD = '''        PlayerStore::playerMutex[playerId].lock();
        const auto pOldPlayerInfo = PlayerStore::playerInfo[playerId].exchange(pPlayerInfo, std::memory_order_acq_rel);

        // PARCHE: el PlayerInfo viejo se limpia CON el mutex tomado.
        // Si se soltaba antes, otro hilo podia borrar un Stream* de estas
        // listas y dejar punteros colgados que despues se recorrian aca.
        if (pOldPlayerInfo != nullptr)
        {
            for (const auto stream : pOldPlayerInfo->listenerStreams)
                stream->DetachListener(playerId);

            for (const auto stream : pOldPlayerInfo->speakerStreams)
                stream->DetachSpeaker(playerId);

            pOldPlayerInfo->listenerStreams.clear();
            pOldPlayerInfo->speakerStreams.clear();
        }

        PlayerStore::playerMutex[playerId].unlock();

        delete pOldPlayerInfo;'''

OLD_REM = '''    PlayerStore::playerMutex[playerId].lock();
    const auto pPlayerInfo = PlayerStore::playerInfo[playerId].exchange(nullptr, std::memory_order_acq_rel);
    PlayerStore::playerMutex[playerId].unlock();

    if (pPlayerInfo != nullptr)
    {
        for (const auto stream : pPlayerInfo->listenerStreams)
            stream->DetachListener(playerId);

        for (const auto stream : pPlayerInfo->speakerStreams)
            stream->DetachSpeaker(playerId);

        delete pPlayerInfo;
    }'''

NEW_REM = '''    PlayerStore::playerMutex[playerId].lock();
    const auto pPlayerInfo = PlayerStore::playerInfo[playerId].exchange(nullptr, std::memory_order_acq_rel);

    // PARCHE (crash al desconectarse): toda la limpieza se hace con el mutex
    // del jugador TOMADO. Antes se soltaba antes de recorrer las listas, y en
    // ese hueco el hilo principal podia llamar a SvDeleteStream() y liberar un
    // Stream* que este hilo todavia estaba recorriendo -> SIGSEGV en
    // PlayerStore::RemovePlayerFromStore.
    // Tomando el mutex durante el recorrido, SvDeleteStream() no puede borrar
    // el flujo hasta que terminemos, porque tiene que pedir este mismo mutex
    // para sacarlo de la lista.
    if (pPlayerInfo != nullptr)
    {
        for (const auto stream : pPlayerInfo->listenerStreams)
            stream->DetachListener(playerId);

        for (const auto stream : pPlayerInfo->speakerStreams)
            stream->DetachSpeaker(playerId);

        pPlayerInfo->listenerStreams.clear();
        pPlayerInfo->speakerStreams.clear();
    }

    PlayerStore::playerMutex[playerId].unlock();

    delete pPlayerInfo;'''

OLD_AL = '''            const auto pPlayerInfo = PlayerStore::RequestPlayerWithSharedAccess(playerId);
            if (pPlayerInfo != nullptr) pPlayerInfo->listenerStreams.insert(stream);
            PlayerStore::ReleasePlayerWithSharedAccess(playerId);

            return stream->AttachListener(playerId);'''

NEW_AL = '''            // PARCHE: solo se anota el flujo si el oyente quedo enganchado de
            // verdad. Antes se anotaba SIEMPRE, incluso en los DynamicStream
            // (cuyo AttachListener devuelve false), y esas entradas fantasma
            // se acumulaban sin borrarse nunca: eran las que despues hacia
            // explotar RemovePlayerFromStore al desconectarse un jugador.
            if (!stream->AttachListener(playerId)) return false;

            const auto pPlayerInfo = PlayerStore::RequestPlayerWithSharedAccess(playerId);
            if (pPlayerInfo != nullptr) pPlayerInfo->listenerStreams.insert(stream);
            PlayerStore::ReleasePlayerWithSharedAccess(playerId);

            return true;'''

OLD_AS = '''            const auto pPlayerInfo = PlayerStore::RequestPlayerWithUniqueAccess(playerId);
            if (pPlayerInfo != nullptr) pPlayerInfo->speakerStreams.insert(stream);
            PlayerStore::ReleasePlayerWithUniqueAccess(playerId);

            return stream->AttachSpeaker(playerId);'''

NEW_AS = '''            // PARCHE: idem hablantes, solo se anota si quedo enganchado.
            if (!stream->AttachSpeaker(playerId)) return false;

            const auto pPlayerInfo = PlayerStore::RequestPlayerWithUniqueAccess(playerId);
            if (pPlayerInfo != nullptr) pPlayerInfo->speakerStreams.insert(stream);
            PlayerStore::ReleasePlayerWithUniqueAccess(playerId);

            return true;'''

sub("PlayerStore.cpp", OLD_ADD, NEW_ADD)
sub("PlayerStore.cpp", OLD_REM, NEW_REM)
sub("main.cpp", OLD_AL, NEW_AL)
sub("main.cpp", OLD_AS, NEW_AS)
print("LISTO: codigo parcheado")

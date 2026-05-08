(function () {
  "use strict";

  const root = document.getElementById("game-ws-root");
  if (!root || !root.dataset.wsUrl) {
    return;
  }

  const devMode = root.dataset.debug === "1";
  const RECONNECT_MS = 2000;
  const STATE_POLL_MS = 4000;

  const logEl = document.getElementById("game-ws-log");
  const chatInput = document.getElementById("game-chat-input");
  const chatSend = document.getElementById("game-chat-send");
  const phaseEl = document.getElementById("game-ws-phase-display");
  const roundEl = document.getElementById("game-ws-round-display");
  const seqEl = document.getElementById("game-ws-seq-display");
  const nightSendKill = document.getElementById("night-send-kill");
  const nightKill = document.getElementById("night-kill-target");
  const nightSendHeal = document.getElementById("night-send-heal");
  const nightHeal = document.getElementById("night-heal-target");
  const nightSendCheck = document.getElementById("night-send-check");
  const nightCheck = document.getElementById("night-check-target");
  const statusEl = document.getElementById("game-ws-status");
  const statusDot = document.getElementById("game-ws-status-dot");
  const copyBtn = document.getElementById("copy-room-code");
  const hintTitleEl = document.getElementById("game-hint-title");
  const hintBodyEl = document.getElementById("game-hint-body");
  const hintPanelEl = document.getElementById("game-hint-panel");
  const phaseTimerEl = document.getElementById("game-phase-timer");
  const lobbyPlayerListEl = document.getElementById("lobby-player-list");
  const lobbyPlayerCountEl = document.getElementById("lobby-player-count");
  const lobbyMaxPlayersEl = document.getElementById("lobby-max-players");
  const lobbyStartFormEl = document.getElementById("lobby-start-form");
  const phaseObjectiveEl = document.getElementById("phase-objective");
  const lobbyReadyProgressEl = document.querySelector(".lobby-ready-progress");

  const PHASE_OBJECTIVES = {
    lobby: "Дождаться заполнения стола и запустить игру",
    night: "Выполнить ночное действие по роли или пропустить ход",
    day_discussion: "Обсудить подозрения в общем чате",
    day_vote: "Выбрать игрока для дневного голосования",
    finished: "Посмотреть итог и вернуться в лобби",
  };

  const PHASE_LABELS = {
    lobby: "Лобби",
    day_discussion: "Обсуждение",
    day_vote: "Голосование",
    night: "Ночь",
    finished: "Игра окончена",
  };
  const NIGHT_ACTION_LABELS = {
    kill: "ночной выбор",
    heal: "защита",
    check: "проверка",
  };

  let reconnectTimer = null;
  let phaseTimerInterval = null;
  let phaseTimeoutRefreshQueued = false;
  let statePollInterval = null;
  let navigationTimer = null;
  let pageUnload = false;
  window.addEventListener("beforeunload", function () {
    pageUnload = true;
  });

  function setWsStatus(connected) {
    if (!statusEl || !statusDot) {
      return;
    }
    if (connected) {
      statusEl.textContent = "Подключено к комнате";
      statusEl.className = "small text-success";
      statusDot.className = "rounded-circle bg-success";
      statusDot.style.width = "0.5rem";
      statusDot.style.height = "0.5rem";
    } else {
      statusEl.textContent = "Нет подключения к комнате";
      statusEl.className = "small text-warning";
      statusDot.className = "rounded-circle bg-danger";
      statusDot.style.width = "0.5rem";
      statusDot.style.height = "0.5rem";
    }
  }

  function setPhaseDisplay(phase) {
    if (!phaseEl || !phase) {
      return;
    }
    phaseEl.textContent = PHASE_LABELS[phase] || phase;
    phaseEl.dataset.phase = phase;
    phaseEl.className =
      "badge phase-pill phase-pill--" + phase + " fs-6 px-3 py-2";
    if (phaseObjectiveEl) {
      phaseObjectiveEl.textContent =
        PHASE_OBJECTIVES[phase] || "Следить за обновлениями фазы";
    }
  }

  function applyHintsFromPayload(payload) {
    if (!hintPanelEl) {
      return;
    }
    const title = payload.hint_title || "";
    const body = payload.hint_body || "";
    if (!title && !body) {
      hintPanelEl.classList.add("d-none");
      return;
    }
    hintPanelEl.classList.remove("d-none");
    if (hintTitleEl) {
      hintTitleEl.textContent = title;
    }
    if (hintBodyEl) {
      hintBodyEl.textContent = body;
    }
  }

  function formatEndsAt(iso) {
    if (!iso || !phaseTimerEl) {
      return;
    }
    const end = Date.parse(iso);
    if (Number.isNaN(end)) {
      phaseTimerEl.textContent = "—";
      return;
    }
    function tick() {
      const left = Math.max(0, end - Date.now());
      const secondsLeft = Math.floor(left / 1000);
      const minutesLeft = Math.floor(secondsLeft / 60);
      const sec = secondsLeft % 60;
      phaseTimerEl.textContent =
        minutesLeft > 0
          ? minutesLeft + " мин " + sec + " с"
          : sec + " с";
      if (left <= 0) {
        window.clearInterval(phaseTimerInterval);
        phaseTimerInterval = null;
        phaseTimerEl.textContent = "истекло";
        queuePhaseTimeoutRefresh();
      }
    }
    if (phaseTimerInterval) {
      window.clearInterval(phaseTimerInterval);
    }
    tick();
    phaseTimerInterval = window.setInterval(tick, 1000);
  }

  function queuePhaseTimeoutRefresh() {
    if (phaseTimeoutRefreshQueued) {
      return;
    }
    phaseTimeoutRefreshQueued = true;
    let skip = false;
    try {
      const key = "mafia:lastPhaseRefreshAt";
      const now = Date.now();
      const last = Number(window.sessionStorage.getItem(key) || "0");
      if (now - last < 8000) {
        skip = true;
      } else {
        window.sessionStorage.setItem(key, String(now));
      }
    } catch (error) {
      // Ignore sessionStorage failures in private mode.
    }
    if (skip) {
      return;
    }
    appendSystemLine("Время фазы истекло. Обновляем состояние игры…");
    softNavigateTo(window.location.href, 1200);
  }

  function syncStateFromPayload(payload) {
    if (payload.phase) {
      setPhaseDisplay(payload.phase);
      root.dataset.phase = payload.phase;
    }
    if (payload.round != null && roundEl) {
      roundEl.textContent = String(payload.round);
    }
    if (payload.seq != null) {
      root.dataset.clientSeq = String(payload.seq);
      if (seqEl) {
        seqEl.textContent = String(payload.seq);
      }
    }
    if (payload.ends_at) {
      root.dataset.endsAt = payload.ends_at;
      if (phaseTimerEl) {
        phaseTimerEl.dataset.endsAt = payload.ends_at;
      }
      formatEndsAt(payload.ends_at);
    }
    applyHintsFromPayload(payload);
  }

  function appendSystemLine(text) {
    if (!logEl) {
      return;
    }
    const line = document.createElement("div");
    line.className = "game-log-line game-log-line--system";
    line.textContent = text;
    logEl.appendChild(line);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function appendChatLine(who, text) {
    if (!logEl) {
      return;
    }
    const line = document.createElement("div");
    line.className = "game-log-line game-log-line--chat";
    const head = document.createElement("strong");
    head.textContent = (who || "?") + ": ";
    line.appendChild(head);
    line.appendChild(document.createTextNode(text || ""));
    logEl.appendChild(line);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function avatarLetter(username) {
    const clean = String(username || "").trim();
    if (!clean) {
      return "?";
    }
    return clean.charAt(0).toUpperCase();
  }

  function syncLobbyStartButton(playerCount) {
    if (!lobbyStartFormEl || !lobbyMaxPlayersEl) {
      return;
    }
    const maxPlayers = Number(lobbyMaxPlayersEl.textContent || "");
    if (!Number.isFinite(maxPlayers) || maxPlayers <= 0) {
      return;
    }
    if (playerCount >= maxPlayers) {
      lobbyStartFormEl.classList.remove("d-none");
      return;
    }
    lobbyStartFormEl.classList.add("d-none");
  }

  function renderLobbyRoster(payload) {
    if (!lobbyPlayerListEl) {
      return;
    }
    const players = Array.isArray(payload.players) ? payload.players : [];
    lobbyPlayerListEl.innerHTML = "";
    players.forEach(function (player) {
      const playerRowElement = document.createElement("li");
      playerRowElement.className = "game-player-row";
      const avatar = document.createElement("span");
      avatar.className = "game-player-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = avatarLetter(player.username);
      const holder = document.createElement("div");
      holder.className = "flex-grow-1 min-w-0";
      const name = document.createElement("span");
      name.className = "fw-medium";
      name.textContent = player.username || "?";
      holder.appendChild(name);
      playerRowElement.appendChild(avatar);
      playerRowElement.appendChild(holder);
      lobbyPlayerListEl.appendChild(playerRowElement);
    });
    if (lobbyPlayerCountEl) {
      lobbyPlayerCountEl.textContent = String(players.length);
    }
    if (lobbyReadyProgressEl) {
      lobbyReadyProgressEl.setAttribute("aria-valuenow", String(players.length));
      const bar = lobbyReadyProgressEl.querySelector(".progress-bar");
      const maxPlayers = Number(
        (lobbyMaxPlayersEl && lobbyMaxPlayersEl.textContent) || "",
      );
      if (bar && Number.isFinite(maxPlayers) && maxPlayers > 0) {
        const pct = Math.max(0, Math.min(100, (players.length / maxPlayers) * 100));
        bar.style.width = String(pct) + "%";
      }
    }
    syncLobbyStartButton(players.length);
  }

  function logSessionJoined(payload) {
    if (devMode) {
      appendSystemLine(
        "[сессия] seq=" +
          payload.seq +
          " · фаза=" +
          (PHASE_LABELS[payload.phase] || payload.phase) +
          " · р=" +
          payload.round,
      );
      return;
    }
    appendSystemLine(
      "Вы в игре. Фаза: " +
        (PHASE_LABELS[payload.phase] || payload.phase) +
        ", раунд " +
        payload.round +
        ".",
    );
  }

  function logPhaseChanged(payload) {
    if (devMode) {
      appendSystemLine(
        "[фаза] " +
          (PHASE_LABELS[payload.phase] || payload.phase) +
          " · р=" +
          payload.round +
          " · seq=" +
          payload.seq +
          " · до " +
          (payload.ends_at || "—"),
      );
      return;
    }
    var msg =
      "Фаза обновлена: " +
      (PHASE_LABELS[payload.phase] || payload.phase) +
      ", раунд " +
      payload.round +
      ".";
    if (payload.ends_at) {
      msg += " Таймер фазы обновлён.";
    }
    appendSystemLine(msg);
  }

  function reloadPage() {
    window.location.reload();
  }

  function clearPendingNavigation() {
    if (!navigationTimer) {
      return;
    }
    window.clearTimeout(navigationTimer);
    navigationTimer = null;
  }

  function softNavigateTo(url, delayMs) {
    if (!url) {
      reloadPage();
      return;
    }
    clearPendingNavigation();
    const mainEl = document.getElementById("main-content");
    if (mainEl) {
      mainEl.classList.add("app-main--transitioning");
      mainEl.setAttribute("aria-busy", "true");
    }
    navigationTimer = window.setTimeout(function () {
      window.location.assign(url);
    }, delayMs);
  }

  function startStatePolling() {
    if (!root.dataset.stateUrl || statePollInterval) {
      return;
    }
    statePollInterval = window.setInterval(function () {
      const stateUrl = root.dataset.stateUrl;
      if (!stateUrl) {
        return;
      }
      fetch(stateUrl, {
        method: "GET",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          if (!r.ok) {
            return null;
          }
          return r.json();
        })
        .then(function (pl) {
          if (!pl) {
            return;
          }
          const localSeq = Number(root.dataset.clientSeq || "0");
          const remoteSeq = Number(pl.seq || "0");
          if (!Number.isFinite(remoteSeq) || remoteSeq <= localSeq) {
            return;
          }
          appendSystemLine("Получено обновление состояния игры.");
          syncStateFromPayload(pl);
          if (pl.win_summary) {
            appendSystemLine("Партия завершена. Показываем итоги партии…");
            softNavigateTo(window.location.href, 900);
            return;
          }
          appendSystemLine("Подготавливаем следующий этап…");
          softNavigateTo(window.location.href, 900);
        })
        .catch(function () {
          // Polling errors are transient; next tick will retry.
        });
    }, STATE_POLL_MS);
  }

  function connectSocket() {
    const gameSocket = new WebSocket(root.dataset.wsUrl);
    root._gameWs = gameSocket;

    gameSocket.addEventListener("open", function () {
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      setWsStatus(true);
      appendSystemLine(
        devMode ? "[канал] подключено" : "Соединение установлено.",
      );
    });

    gameSocket.addEventListener("close", function () {
      setWsStatus(false);
      if (pageUnload) {
        return;
      }
      appendSystemLine(
        devMode ? "[канал] отключено" : "Соединение прервано. Переподключение…",
      );
      if (!reconnectTimer) {
        reconnectTimer = window.setTimeout(function () {
          reconnectTimer = null;
          connectSocket();
        }, RECONNECT_MS);
      }
    });

    gameSocket.addEventListener("message", function (ev) {
      console.log("🔵 СООБЩЕНИЕ ПОЛУЧЕНО:", ev.data);

      let data;
      try {
        data = JSON.parse(ev.data);
      } catch (error) {
        appendSystemLine(
          devMode
            ? "[ошибка] не JSON: " + String(ev.data).slice(0, 200)
            : "Получено некорректное сообщение от сервера.",
        );
        return;
      }

      if (data.last_night_result && Object.keys(data.last_night_result).length > 0) {
          console.log("🔥 НАЙДЕН last_night_result:", data.last_night_result);
          // Здесь будет логика отображения
      }

      if (data.last_night_result && data.phase === 'day_discussion') {
          const res = data.last_night_result;
          const myRole = root.dataset.role;
          let message = "";
          let alertClass = "alert-info";

          if (myRole === 'mafia' && res.action === 'kill') {
              message = res.success 
                  ? "Цель успешно устранена." 
                  : (res.was_healed ? "Доктор спас вашу жертву!" : "Покушение сорвалось.");
              alertClass = "alert-danger";
          } else if (myRole === 'doctor' && res.action === 'heal') {
              message = res.success 
                  ? "Вы спасли жизнь!" 
                  : "Вы лечили игрока, но на него не нападали.";
              alertClass = "alert-success";
          } else if (myRole === 'sheriff' && res.action === 'check') {
              message = "Результат проверки: " + res.target_name + " — " + (res.is_mafia ? "МАФИЯ" : "Мирный");
          }

          const container = document.getElementById('private-notifications');
          if (message && container) {
              container.innerHTML = `
                  <div class="alert ${alertClass} alert-dismissible fade show shadow-sm border-0 mb-3">
                      <small class="fw-bold text-uppercase" style="font-size: 0.7rem;">Личный отчет ночи</small><br>
                      ${message}
                      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                  </div>`;
              
              setTimeout(() => {
                  const alert = container.querySelector('.alert');
                  if (alert) alert.remove();
              }, 8000);
          }
      }

      const eventType = data.type;
      const payload = data.payload || {};
      if (eventType === "session.joined") {
        logSessionJoined(payload);
        syncStateFromPayload(payload);

         if (payload.last_night_result && Object.keys(payload.last_night_result).length > 0) {
            const res = payload.last_night_result;
            const myRole = root.dataset.role;
            let message = "";
            let alertClass = "alert-info";
            
            if (myRole === 'mafia' && res.action === 'kill') {
                message = res.success 
                    ? "Цель успешно устранена." 
                    : (res.was_healed ? "Доктор спас вашу жертву!" : "Покушение сорвалось.");
                alertClass = "alert-danger";
            } else if (myRole === 'doctor' && res.action === 'heal') {
                message = res.success 
                    ? "Вы спасли жизнь!" 
                    : "Вы лечили игрока, но на него не нападали.";
                alertClass = "alert-success";
            } else if (myRole === 'sheriff' && res.action === 'check') {
                message = "Результат проверки: " + res.target_name + " — " + (res.is_mafia ? "МАФИЯ" : "Мирный");
            }
            
            if (message) {
                const container = document.getElementById('private-notifications');
                if (container) {
                    container.innerHTML = `
                        <div class="alert ${alertClass} alert-dismissible fade show shadow-sm border-0 mb-3">
                            <small class="fw-bold text-uppercase" style="font-size: 0.7rem;">Личный отчет ночи</small><br>
                            ${message}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>`;
                    
                    setTimeout(() => {
                        const alert = container.querySelector('.alert');
                        if (alert) alert.remove();
                    }, 8000);
                }
            }
        }

        if (payload.win_summary) {
          appendSystemLine(
            devMode
              ? "[итог] " + JSON.stringify(payload.win_summary)
              : "Игра уже завершена.",
          );
        }
        return;
      }
      if (eventType === "phase_changed") {
        logPhaseChanged(payload);
        syncStateFromPayload(payload);
        phaseTimeoutRefreshQueued = false;
        if (payload.win_summary) {
          appendSystemLine(
            devMode
              ? "[итог] " + JSON.stringify(payload.win_summary)
              : "Партия завершена. Показываем итоги партии…",
          );
          softNavigateTo(window.location.href, 900);
          return;
        }
        appendSystemLine("Подготавливаем следующий этап…");
        softNavigateTo(window.location.href, 900);
        return;
      }
      if (data.last_night_result && data.phase === 'day_discussion') {
          const res = data.last_night_result;
          const myRole = root.dataset.role;
          let message = "";
          let alertClass = "alert-info";

          if (myRole === 'mafia' && res.action === 'kill') {
              message = res.success 
                  ? "Цель успешно устранена." 
                  : (res.was_healed ? "Доктор спас вашу жертву!" : "Покушение сорвалось.");
              alertClass = "alert-danger";
          } else if (myRole === 'doctor' && res.action === 'heal') {
              message = res.success 
                  ? "Вы спасли жизнь этой ночью!" 
                  : "Вы лечили игрока, но на него не нападали.";
              alertClass = "alert-success";
          } else if (myRole === 'sheriff' && res.action === 'check') {
              message = "Результат проверки: игрок " + res.target_name + " — " + (res.is_mafia ? "МАФИЯ" : "Мирный");
          }

          if (message) {
              const container = document.getElementById('private-notifications');
              if (container) {
                  container.innerHTML = `
                      <div class="alert ${alertClass} alert-dismissible fade show shadow-sm border-0 mb-3">
                          <small class="fw-bold text-uppercase" style="font-size: 0.7rem;">Личный отчет ночи</small><br>
                          ${message}
                          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                      </div>`;
                  
                  setTimeout(() => {
                      const alert = container.querySelector('.alert');
                      if (alert) alert.remove();
                  }, 8000);
              }
          }
          return;
      }
      if (eventType === "votes_updated") {
        appendSystemLine(
          devMode ? "[голоса] обновление" : "Голоса обновлены. Синхронизируем экран…",
        );
        softNavigateTo(window.location.href, 700);
        return;
      }
      if (eventType === "lobby.roster") {
        renderLobbyRoster(payload);
        appendSystemLine(
          devMode
            ? "[лобби] состав: "
                + (payload.count != null ? payload.count : "?")
            : "Состав игроков в лобби обновлён.",
        );
        return;
      }
      if (eventType === "chat.message") {
        const authorLabel =
          payload.username || payload.user_id || "?";
        appendChatLine(authorLabel, payload.text || "");
        return;
      }
      if (eventType === "evidence.batch") {
        appendSystemLine(
          devMode
            ? "[улики] раунд "
                + payload.round
                + " · шт.: "
                + (payload.items || []).length
            : "Новые улики. Синхронизируем экран…",
        );
        softNavigateTo(window.location.href, 700);
        return;
      }
      if (eventType === "night.action.ack") {
        const kind = payload.kind;
        const label = NIGHT_ACTION_LABELS[kind] || "ночное действие";
        appendSystemLine(
          devMode
            ? "[ночь] действие принято: " + String(kind || "?")
            : "Ваш " + label + " зафиксирован.",
        );
        return;
      }

      if (eventType === "private.result") {
         console.log("🔔 private.result received:", payload);
          const myRole = root.dataset.role;
          const res = payload;
          let message = "";
          let alertClass = "alert-info";

          if (myRole === 'mafia' && res.action === 'kill') {
              message = res.success 
                  ? "Цель успешно устранена." 
                  : (res.was_healed ? "Доктор спас вашу жертву!" : "Покушение сорвалось.");
              alertClass = "alert-danger";
          } else if (myRole === 'doctor' && res.action === 'heal') {
              message = res.success 
                  ? "Великолепно! Вы спасли жизнь этой ночью." 
                  : "Вы лечили игрока, но на него не нападали.";
              alertClass = "alert-success";
          } else if (myRole === 'sheriff' && res.action === 'check') {
              const roleText = res.is_mafia ? "МАФИЯ" : "Мирный житель";
              message = `Результат проверки: ${res.target_name} — ${roleText}`;
              alertClass = res.is_mafia ? "alert-warning" : "alert-info";
          }

          if (message) {
              const privateContainer = document.getElementById('private-notifications');
              if (privateContainer) {
                  privateContainer.innerHTML = `
                      <div class="alert ${alertClass} alert-dismissible fade show shadow-sm border-0 mb-3 animate__animated animate__fadeIn">
                          <small class="fw-bold text-uppercase" style="font-size: 0.7rem;">Личный отчет ночи</small><br>
                          ${message}
                          <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                      </div>`;
                  
                  setTimeout(() => {
                      const alert = privateContainer.querySelector('.alert');
                      if (alert) {
                          alert.classList.remove('show');
                          setTimeout(() => {
                              if (privateContainer.innerHTML === alert.outerHTML) {
                                  privateContainer.innerHTML = '';
                              }
                          }, 150);
                      }
                  }, 8000);
              } else {
                  appendSystemLine(message);
              }
          }
          return;
      }

      if (eventType === "pong") {
        if (devMode) {
          appendSystemLine("[pong] " + (payload.ts || ""));
        }
        return;
      }
      if (eventType === "error") {
        if (devMode) {
          appendSystemLine("[ошибка] " + JSON.stringify(payload));
        } else {
          const code = payload.code;
          let human =
            payload.message ||
            {
              wrong_phase: "В этой фазе действие недоступно.",
              rate_limited: "Слишком частые сообщения — подождите немного.",
              forbidden: "Действие для вас сейчас запрещено.",
              not_found: "Комната не найдена.",
              bad_payload: "Некорректные данные.",
              bad_target: "Недопустимая цель.",
              doctor_same_target_twice:
                "Доктор не может лечить того же игрока две ночи подряд.",
              unknown_kind: "Неизвестный тип ночного действия.",
            }[code];
          if (!human) {
            human = "Не удалось выполнить действие. Попробуйте ещё раз.";
          }
          appendSystemLine(human);
        }
        return;
      }
      if (devMode) {
        appendSystemLine(
          "[?] "
            + eventType
            + " "
            + JSON.stringify(payload).slice(0, 400),
        );
      }
    });
  }

  connectSocket();
  startStatePolling();

  if (chatSend && chatInput) {
    chatSend.addEventListener("click", function () {
      const text = (chatInput.value || "").trim();
      const gameSocket = root._gameWs;
      if (
        !text
        || !gameSocket
        || gameSocket.readyState !== WebSocket.OPEN
      ) {
        return;
      }
      gameSocket.send(
        JSON.stringify({ type: "chat.message", payload: { text: text } }),
      );
      chatInput.value = "";
    });
    chatInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatSend.click();
      }
    });
  }

  function sendNightAction(kind, selectEl) {
    const gameSocket = root._gameWs;
    if (
      !gameSocket
      || gameSocket.readyState !== WebSocket.OPEN
      || !selectEl
    ) {
      appendSystemLine("Нет соединения с сервером. Подождите переподключение.");
      return;
    }
    const selectedTargetId = selectEl.value;
    if (!selectedTargetId) {
      appendSystemLine("Сначала выберите игрока из списка.");
      return;
    }
    gameSocket.send(
      JSON.stringify({
        type: "night.action",
        payload: { kind: kind, target_id: selectedTargetId },
      }),
    );
  }

  if (nightSendKill && nightKill) {
    nightSendKill.addEventListener("click", function () {
      sendNightAction("kill", nightKill);
    });
  }
  if (nightSendHeal && nightHeal) {
    nightSendHeal.addEventListener("click", function () {
      sendNightAction("heal", nightHeal);
    });
  }
  if (nightSendCheck && nightCheck) {
    nightSendCheck.addEventListener("click", function () {
      sendNightAction("check", nightCheck);
    });
  }

  if (copyBtn && copyBtn.dataset.code) {
    copyBtn.addEventListener("click", function () {
      const code = copyBtn.dataset.code;
      const label = copyBtn.textContent;
      function done() {
        copyBtn.textContent = "Скопировано";
        copyBtn.classList.remove("btn-outline-secondary");
        copyBtn.classList.add("btn-success");
        window.setTimeout(function () {
          copyBtn.textContent = label;
          copyBtn.classList.add("btn-outline-secondary");
          copyBtn.classList.remove("btn-success");
        }, 1600);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(code).then(done).catch(function () {
          if (logEl) {
            appendSystemLine(
              devMode
                ? "[буфер] не удалось скопировать"
                : "Не удалось скопировать в буфер.",
            );
          }
        });
      } else if (logEl) {
        appendSystemLine(
          devMode
            ? "[буфер] недоступен в этом браузере"
            : "Копирование в буфер недоступно в этом браузере.",
        );
      }
    });
  }

  const initialEnds =
    root.dataset.endsAt ||
    (phaseTimerEl && phaseTimerEl.dataset.endsAt) ||
    "";
  if (initialEnds) {
    formatEndsAt(initialEnds);
  }
})();

// Serverless endpoint → GET /api/data
// Arsenal: football-data.org (needs FOOTBALLDATA_KEY env var)
// Spartak / Fakel: scraped live from sports.ru team calendar pages
//   (api-football's free plan does not cover the 2026/27 season at all,
//   see project history — sports.ru's calendar page carries every
//   tournament for a team, with real kickoff times once confirmed).
const cheerio = require("cheerio");

const FD_KEY = process.env.FOOTBALLDATA_KEY || "";
const SEASON = 2026;
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

const MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

const FALLBACK_CRESTS = {
  arsenal: "https://upload.wikimedia.org/wikipedia/en/5/53/Arsenal_FC.svg",
  spartak: "https://upload.wikimedia.org/wikipedia/en/5/50/FC_Spartak_Moscow.svg",
  fakel: "https://upload.wikimedia.org/wikipedia/en/f/f6/FC_Fakel_Voronezh.svg",
};

const CLUBS_META = {
  arsenal: {
    name: "Арсенал",
    league: "АПЛ · Сезон 2026/27",
    bodyClass: "club-arsenal",
    swatchColor: "#EF0107",
    tournaments: ["АПЛ 26/27"],
    hasRussian: false,
    noLeagueNote: null,
  },
  spartak: {
    name: "Спартак Москва",
    league: "РПЛ · Сезон 2026/27",
    bodyClass: "club-spartak",
    swatchColor: "#C8102E",
    tournaments: ["Товарищеские матчи", "Суперкубок России", "РПЛ 26/27", "Кубок России 26/27"],
    hasRussian: true,
    noLeagueNote: null,
  },
  fakel: {
    name: "Факел Воронеж",
    league: "РПЛ · Сезон 2026/27",
    bodyClass: "club-fakel",
    swatchColor: "#005B99",
    tournaments: ["РПЛ 26/27", "Кубок России 26/27"],
    hasRussian: true,
    noLeagueNote: "По данным Wikipedia, Факел возвращается в РПЛ в сезоне 2026/27.",
  },
};

// sports.ru tournament slug (from the calendar row's /tournament/<slug>/ link) → our tab name
const TOURNAMENT_MAP = {
  "club-friendlies": "Товарищеские матчи",
  "russian-super-cup": "Суперкубок России",
  rfpl: "РПЛ 26/27",
  "russian-cup": "Кубок России 26/27",
};

const SPORTSRU_CLUB_NAME = { spartak: "Спартак", fakel: "Факел" };

// ── generic fetch helpers ────────────────────────────────────────────────

async function fetchWithTimeout(url, opts = {}, ms = 10000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: ctrl.signal });
  } finally {
    clearTimeout(t);
  }
}

async function fetchJson(url, headers) {
  try {
    const r = await fetchWithTimeout(url, { headers });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    console.warn(`[WARN] ${url} -> ${e}`);
    return null;
  }
}

async function fetchText(url) {
  try {
    const r = await fetchWithTimeout(url, {
      headers: { "User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9" },
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.text();
  } catch (e) {
    console.warn(`[WARN] ${url} -> ${e}`);
    return null;
  }
}

function resultTag(hs, as_, isHome) {
  if (hs == null || as_ == null) return null;
  if (isHome) return hs > as_ ? "win" : hs === as_ ? "draw" : "loss";
  return as_ > hs ? "win" : hs === as_ ? "draw" : "loss";
}

// ── football-data.org (Arsenal) ──────────────────────────────────────────

const MSK_TZ = "Europe/Moscow";

function toMskParts(isoStr) {
  const dt = new Date(isoStr);
  const fmt = new Intl.DateTimeFormat("en-GB", {
    timeZone: MSK_TZ,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = fmt.formatToParts(dt).reduce((a, p) => ((a[p.type] = p.value), a), {});
  return parts;
}

function fmtDate(isoStr) {
  const p = toMskParts(isoStr);
  return `${parseInt(p.day, 10)} ${MONTHS[parseInt(p.month, 10) - 1]}`;
}

function fmtTime(isoStr) {
  const p = toMskParts(isoStr);
  return `${p.hour}:${p.minute}`;
}

async function fetchFdTeamCrest(teamId) {
  if (!FD_KEY) return null;
  const data = await fetchJson(`https://api.football-data.org/v4/teams/${teamId}`, {
    "X-Auth-Token": FD_KEY,
  });
  return data?.crest || null;
}

async function fetchEplFixtures(teamId, competition) {
  if (!FD_KEY) return [];
  const data = await fetchJson(
    `https://api.football-data.org/v4/teams/${teamId}/matches?competitions=${competition}&season=${SEASON}&status=SCHEDULED,FINISHED,LIVE`,
    { "X-Auth-Token": FD_KEY }
  );
  if (!data || !data.matches) return [];
  return data.matches.map((m) => {
    const isHome = m.homeTeam.id === teamId;
    const hs = m.score.fullTime.home;
    const as_ = m.score.fullTime.away;
    const done = m.status === "FINISHED";
    return {
      date: fmtDate(m.utcDate),
      time: fmtTime(m.utcDate),
      home: m.homeTeam.shortName || m.homeTeam.name,
      away: m.awayTeam.shortName || m.awayTeam.name,
      homeGame: isHome,
      score: done && hs != null ? `${hs}-${as_}` : null,
      result: done ? resultTag(hs, as_, isHome) : null,
    };
  });
}

async function fetchEplStandings(competition, highlightId) {
  if (!FD_KEY) return [];
  const data = await fetchJson(
    `https://api.football-data.org/v4/competitions/${competition}/standings?season=${SEASON}`,
    { "X-Auth-Token": FD_KEY }
  );
  let table;
  try {
    table = data.standings[0].table;
  } catch {
    return [];
  }
  const CL = new Set([1, 2, 3, 4]);
  const EL = new Set([5, 6, 7]);
  const REL = new Set([18, 19, 20]);
  return table.map((r) => ({
    pos: r.position,
    name: r.team.shortName || r.team.name,
    crest: r.team.crest || null,
    pts: r.points,
    w: r.won,
    d: r.draw,
    l: r.lost,
    zone: CL.has(r.position) ? "cl" : EL.has(r.position) ? "el" : REL.has(r.position) ? "rel" : null,
    highlight: r.team.id === highlightId,
  }));
}

async function buildArsenal() {
  const meta = CLUBS_META.arsenal;
  const teamId = 57;
  const [fdCrest, games, standings] = await Promise.all([
    fetchFdTeamCrest(teamId),
    fetchEplFixtures(teamId, "PL"),
    fetchEplStandings("PL", teamId),
  ]);
  return {
    ...meta,
    crest: fdCrest || FALLBACK_CRESTS.arsenal,
    hasData: games.length > 0,
    games: { "АПЛ 26/27": games },
    standings: {
      note: standings.length
        ? "Таблица актуальна на момент последнего обновления"
        : "Сезон 26/27 стартует 21 августа — таблица пустая",
      teams: standings,
    },
  };
}

// ── sports.ru (Spartak / Fakel) ──────────────────────────────────────────

function parseDateLink(text) {
  // "08.07.2026" or "08.07.2026 | 19:30"
  const m = text.match(/(\d{2})\.(\d{2})\.(\d{4})(?:\s*\|\s*(\d{2}:\d{2}))?/);
  if (!m) return null;
  const [, dd, mm, yyyy, time] = m;
  return {
    day: parseInt(dd, 10),
    month: parseInt(mm, 10),
    year: parseInt(yyyy, 10),
    time: time || null,
  };
}

async function fetchSportsRuGames(slug, clubName) {
  const html = await fetchText(`https://www.sports.ru/football/club/${slug}/calendar/`);
  if (!html) return {};
  const $ = cheerio.load(html);

  let $table = null;
  $("table").each((_, t) => {
    if ($(t).find("td.score-td").length) {
      $table = $(t);
      return false;
    }
  });
  if (!$table) return {};

  const buckets = {};
  $table
    .find("tr")
    .slice(1) // skip header row ("Дата" / "Турнир" / …)
    .each((_, tr) => {
      const $tr = $(tr);

      const dateText = $tr.find("td.bordR a").first().text().replace(/\s+/g, " ").trim();
      const parsed = parseDateLink(dateText);
      if (!parsed) return;

      const tourHref = $tr.find('td.name-td a[href*="/tournament/"]').first().attr("href") || "";
      const tourSlugMatch = tourHref.match(/\/tournament\/([a-z0-9-]+)\//);
      const bucket = tourSlugMatch ? TOURNAMENT_MAP[tourSlugMatch[1]] : null;
      if (!bucket) return; // unrecognised competition — skip rather than mis-bucket it

      const opponent = $tr.find("i.icon-flag").nextAll("a[title]").first().text().trim();
      if (!opponent) return;

      const homeAwayText = $tr.find("td.padR20").first().text().trim();
      const isHome = homeAwayText === "Дома";

      const scoreText = $tr.find("td.score-td a.score b").first().text().replace(/\s+/g, "").trim();
      let score = null;
      let hs = null;
      let as_ = null;
      const sm = scoreText.match(/(\d+):(\d+)/);
      if (sm) {
        hs = parseInt(sm[1], 10);
        as_ = parseInt(sm[2], 10);
        score = `${hs}-${as_}`;
      }

      const game = {
        date: `${parsed.day} ${MONTHS[parsed.month - 1]}`,
        time: parsed.time,
        home: isHome ? clubName : opponent,
        away: isHome ? opponent : clubName,
        homeGame: isHome,
        score,
        result: score ? resultTag(hs, as_, isHome) : null,
        _ts: Date.UTC(parsed.year, parsed.month - 1, parsed.day),
      };
      (buckets[bucket] = buckets[bucket] || []).push(game);
    });

  for (const key of Object.keys(buckets)) {
    buckets[key].sort((a, b) => a._ts - b._ts).forEach((g) => delete g._ts);
  }
  return buckets;
}

async function buildRplClub(key) {
  const meta = CLUBS_META[key];
  const clubName = SPORTSRU_CLUB_NAME[key];
  const buckets = await fetchSportsRuGames(key, clubName);
  const games = {};
  for (const t of meta.tournaments) games[t] = buckets[t] || [];
  const hasData = Object.values(games).some((arr) => arr.length > 0);
  return {
    ...meta,
    crest: FALLBACK_CRESTS[key],
    hasData,
    games,
    standings: {
      note: "Сезон 2026/27 стартует 25 июля — таблица пока не сформирована",
      teams: [],
    },
  };
}

// ── handler ───────────────────────────────────────────────────────────────

module.exports = async (req, res) => {
  try {
    const [arsenal, spartak, fakel] = await Promise.all([
      buildArsenal(),
      buildRplClub("spartak"),
      buildRplClub("fakel"),
    ]);
    res.setHeader(
      "Cache-Control",
      "public, max-age=0, s-maxage=1800, stale-while-revalidate=600"
    );
    res.status(200).json({
      updated: new Date().toISOString(),
      clubs: { arsenal, spartak, fakel },
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
};

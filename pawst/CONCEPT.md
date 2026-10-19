# Pawst — concept v0.1

**Mail at the speed of nature.**

Pawst is a slow messenger. You write a letter, pick an animal, and the animal
carries it to your friend. Unlike Roost (birds, straight line, time = distance /
speed), Pawst animals travel **real routes** (roads, trails, sea lanes, flight
hops), they **rest and eat**, and they can **hand the letter over** to another
animal or to booked transport (ship, plane, car, ark). A hamster can ride a
dolphin. That is the whole product.

This document is the simplified, build-it-with-two-people version. Everything
that needs a GIS team is cut.

---

## 1. What we keep (the idea)

1. **Real routes, not straight lines.**
   - Land animals follow real roads and trails (OpenRouteService / OSRM).
   - Water animals follow real shipping lanes (the open-source `searoute` graph).
   - Flying animals fly great-circle, but only in hops up to their max leg
     length; each hop ends on land with a rest. A pigeon cannot cross the
     Atlantic. An albatross can.
2. **Animals rest.** Every animal has a daily activity budget and a meal
   interval. The journey timeline shows "resting near Linz", "snack break",
   "sleeping, continues at 06:00".
3. **Relays / piggyback.** A journey is a chain of legs. Each leg has a carrier:
   an animal or a vehicle. The planner builds the chain automatically around
   hubs (ports, airports) and the user can swap any leg's carrier.
4. **Collection + XP.** Animals are unlocked with XP earned by sending and
   receiving. Extinct animals (mammoth, T. rex, pteranodon, megalodon) are the
   late-game rewards.

## 2. What we cut (v2 or never)

| Cut | Why |
|---|---|
| Seasons, migration calendars, hibernation | Needs species data and a calendar engine; nobody will notice in month one. |
| Terrain cost grids, land cover, wind, ocean currents | This is the GIS project. Roads + sea lanes are "real enough". |
| Live Movebank / eBird data | Use published numbers once, by hand, to fill the animal table. |
| Paleogeography for extinct animals | A mammoth walking through present-day Germany is funnier anyway. |
| Rivers as water routes | Sea lanes only. |
| Continuous simulation | The journey is computed **once at send time** into a list of timestamped events. The client interpolates. |
| Photos, group chats, pen pals | Later. Text letters only. |

## 3. How a journey is planned

Input: sender location (city centroid), recipient location, chosen animal,
optional boosts. Output: `legs[]` and `events[]` with timestamps.

```
plan(from, to, animal, boosts):
  if animal.domain == "land":
      route = landRoute(from, to)                 # ORS foot-walking profile
      if route exists: legs = [animalLeg(route)]
      else:                                       # different landmass
          portA = nearestPort(from); portB = nearestPort(to)
          legs = [ animalLeg(landRoute(from, portA)),
                   seaLeg(portA, portB, carrier = boosts.sea ?? "ship"),
                   animalLeg(landRoute(portB, to)) ]
  if animal.domain == "water":
      portA = nearestPort(from); portB = nearestPort(to)
      companion = boosts.landCompanion ?? "snail"   # the piggyback
      legs = [ animalLeg(landRoute(from, portA), companion),
               animalLeg(seaRoute(portA, portB), animal),
               animalLeg(landRoute(portB, to), companion) ]
  if animal.domain == "air":
      hops = splitGreatCircle(from, to, animal.maxLegKm)   # each hop must end on land
      if a hop has no land to end on and hop > maxLegKm:
          insert sea leg (ship / water animal) between nearest ports
      legs = hops.map(animalLeg)
  events = schedule(legs)     # see below
  return { legs, events, arrivesAt: last(events).at }
```

`schedule(legs)` walks each leg: move for `activeHoursPerDay`, insert a
`meal` event every `mealEveryHours`, then a `rest` event until the next day
starts. Vehicles have departure cadence instead of rest: a ship leaves every
12 h, a plane every 6 h, so the letter "waits at the port", which is a feature.

Booked transport replaces a leg's carrier and costs coins:

| Vehicle | Domain | Speed | Cadence | Notes |
|---|---|---|---|---|
| Car | land | 70 km/h | instant | Uses driving profile instead of walking. |
| Ship | water | 35 km/h | every 12 h | Port to port. |
| Plane | air | 800 km/h | every 6 h | Airport to airport; planner adds land legs to/from airports. |
| Ark | water | 10 km/h | every 24 h | Free, slow, carries any animal. XP unlock. Pure joke, keep it. |

## 4. Animal table (MVP seed)

Numbers are rounded from real-world figures; good enough. `maxLegKm` applies
only to air. `activeHours` is per 24 h. See `animals.json` for the machine
version.

| Animal | Domain | km/h | Active h/day | Meal every h | Max leg km | Unlock |
|---|---|---|---|---|---|---|
| Microbe | land | 0.0001 | 24 | — | — | free (works only within ~10 m, "send to the person next to you") |
| Snail | land | 0.05 | 8 | 2 | — | free |
| Hamster | land | 2 | 6 | 1 | — | free |
| Tortoise | land | 0.3 | 8 | 3 | — | free |
| Husky | land | 15 | 10 | 4 | — | 100 XP |
| Horse | land | 20 | 8 | 3 | — | 300 XP |
| Elephant | land | 6 | 14 | 1 | — | 600 XP |
| Pigeon | air | 80 | 10 | 4 | 1000 | free |
| Swift | air | 100 | 20 | 6 | 3000 | 200 XP |
| Albatross | air | 60 | 16 | 8 | 6000 | 500 XP |
| Sea turtle | water | 2 | 24 | 6 | — | free |
| Dolphin | water | 15 | 20 | 2 | — | 200 XP |
| Mammoth | land | 5 | 10 | 1 | — | 1500 XP |
| T. rex | land | 20 | 4 | 2 | — | 2000 XP (eats constantly, long "feast" events) |
| Pteranodon | air | 50 | 12 | 4 | 2000 | 2000 XP |
| Megalodon | water | 20 | 18 | 1 | — | 2500 XP |

Worked example, Prague → Lisbon (~2 600 km by road):
- Horse: 20 km/h × 8 h = 160 km/day → ~16 days, with daily rest and meals.
- Pigeon: 3 hops of ~870 km, 80 km/h × 10 h = 800 km/day → ~3.5 days.
- Hamster on dolphin: hamster to Hamburg port (~7 days), dolphin Hamburg →
  Lisbon sea lane (~2 400 km / 15 km/h / 20 h ≈ 8 days), hamster last mile.
- Pigeon + booked plane: pigeon to Prague airport, plane (wait ≤ 6 h, 3 h
  flight), pigeon from Lisbon airport → same day.

## 5. Product scope (MVP screens)

1. **Onboarding** — email or Apple/Google login, pick home city. Location is
   city-level only (like Roost), never exact.
2. **Friends** — add by username or QR.
3. **Compose** — pick friend → pick animal → optional boost → route preview
   with ETA → send.
4. **Journey** — map with the animal's current position (interpolated from
   events), timeline of events, push notification on key events (departed,
   resting, boarded ship, arrived).
5. **Inbox** — delivered letters with journey replay.
6. **Stable** — owned animals, XP, unlocks, coins.

## 6. Tech stack for one or two people

| Layer | Pick | Why |
|---|---|---|
| App | Expo (React Native) + TypeScript | One codebase, iOS + Android, OTA updates. |
| Backend | Supabase (Auth, Postgres, Storage, pg_cron) | Zero ops. |
| Planner | Small Python service (FastAPI on Fly.io / Railway) | `searoute` is Python; ORS has a Python client; one `POST /plan` endpoint. |
| Land routing | OpenRouteService API (free tier, 2000 req/day) | Walking and driving profiles. Switch to self-hosted OSRM if it ever matters. |
| Sea routing | `searoute` (PyPI) | Shortest path on a real sea-lane graph, returns GeoJSON. |
| Hubs | `searoute` port list, OurAirports CSV (large + medium airports) | Both free. |
| Map | MapLibre via `@maplibre/maplibre-react-native`, tiles from MapTiler / Protomaps free tier | No Mapbox bill. |
| Push | Expo Push + a pg_cron job every minute that sends notifications for events whose time has passed | No worker process. |
| Payments | RevenueCat | Coins + animal packs on both stores. |

Nothing runs continuously. Sending a letter calls the planner once, stores
`legs` and `events`, and that is it.

## 7. Data model

```
users           (id, username, home_city, home_lat, home_lng, xp, coins)
friendships     (user_id, friend_id, status)
animals         static JSON shipped with the app (see animals.json)
user_animals    (user_id, animal_id, unlocked_at)
journeys        (id, sender_id, recipient_id, body, animal_id,
                 legs jsonb, events jsonb, departs_at, arrives_at,
                 delivered boolean)
```

`events` entry: `{ at, type: "depart"|"move"|"meal"|"rest"|"wait"|"board"|"arrive", lat, lng, carrier, note }`.

## 8. Monetization

Coins for booked transport (car, ship, plane). Animal packs. Extinct animals
via XP or coins. Free users get the free tier animals and can earn everything
with XP. Same shape as Roost.

## 9. Four-week build plan

| Week | Deliverable |
|---|---|
| 1 | Planner service: land + air legs, rest schedule, `animals.json`, CLI that prints a timeline for two cities. |
| 2 | Expo shell: auth, friends, compose, calls the planner, stores journeys. |
| 3 | Journey screen: map + interpolated position + timeline; push via pg_cron. |
| 4 | Sea legs, piggyback chains, booked transport, XP/unlocks, store listing. |

## 10. Name

**Pawst** — "post" with a paw in it. Short, one syllable, no existing app or
company found with that name in web search. Tagline: *Mail at the speed of nature.*

Alternatives considered (all had collisions or were weaker):
- *Tagalong* — fits the piggyback idea, but an iOS social app and several
  startups already use it.
- *Piggyback* — same, a 2016 NY messaging startup used it; generic word.
- *Hopalong*, *Wildway*, *Critter Courier* — free of collisions in search,
  but longer or less distinctive.

### Domains

Live WHOIS/RDAP checks were not possible from the environment this was
written in, so availability below is **unverified**. Check at Porkbun or
Namecheap before buying.

| Domain | Note |
|---|---|
| pawst.app | First choice. `.app` is HTTPS-only, fine for an app landing page. |
| pawst.com | Likely taken or parked; check anyway. |
| pawst.io / pawst.co | Backups. |
| pawst.world / pawst.earth | Thematic backups; `.earth` fits the pitch. |
| getpawst.com | Fallback if `.com` is parked. |

`.nature` is not a delegated top-level domain (only `.natura` ever existed, a
brand TLD revoked in 2024), so there is nothing to buy there. Nature-flavoured
TLDs that do exist: `.earth`, `.world`, `.eco`, `.life`, `.pet`.

Also search the App Store and Google Play for "Pawst" and the EUIPO / USPTO
trademark databases before committing to the name.

// @section New characters: Eggusz (person 51) in the subway, chapter 2
// @description Adds brand-new characters to story mode (docs/PLAN-new-characters.md). Eggusz (person and template 51, a slot left over from a cut character editor): bald, black mustache, red leather jacket, jeans, black sneakers; Jason G's fighting style; level 12, 3000 HP, Pride 200, attack x1.0, $1000. He stands around in the ABANDONED SUBWAY STATION (area 5) during chapter 2 (story stage 6) like any street person: walk up, fight him, RECRUIT him. Everything about a character is one row of the tables in mods/c/new_characters.c.
// @org 0x000A1000
// @max 0x1000
// @bss 0x000E1000 0x1000
// @hook Text_Get NC_TextGet
// @jump Preset_Get NC_PresetGet
// @hook Person_Init NC_PersonInit
// @hook Area_BuildPeople NC_BuildPeople
// @hook NpcSpawn_Step NC_NpcSpawnStep

#include "game.h"

const char *orig_Text_Get(int text_id, int zero);
void orig_Person_Init(int slot, int person_def, int temp);
void *orig_Area_BuildPeople(void);
int orig_NpcSpawn_Step(int phase, s16 *request);

#define TEXT_PERSON_NAME 11001   /* a person's name is text 11001 + person id (Fighter_DisplayName) */
#define MAX_SLOTS 22

/* ---- The characters ---------------------------------------------------------------------------------- */

/* One outfit slot: g_ItemTable item (its +0x10 is a DATA.XAF mesh) and the DATA.XAF textures it uses,
 * ending -1. A preset lists its slots without gaps: the first item < 1 ends the list (Person_Init). */
typedef struct {
    s16 item;
    s16 parts[16];
} NewSlot;

typedef struct {
    s16 person;           /* person and template id: a saved person 0-199 nobody uses (51, 52) */
    s16 preset;           /* outfit preset number: one no template uses (87, 94, 97, 127, 129, 132, 141, 143,
                             1, 19, 20), so the game's per-preset tables have a normal entry for it */
    s16 base_template;    /* template copied first; the fields below replace its values */
    s16 body_preset;      /* preset whose body params (+0x318) are copied: sets the body build */
    u16 class_row;        /* moves: row in g_ClassTable */
    s8 level;
    u8 kind;              /* PersonDef.kind: keep 0 (5 = story boss: no talk after the knockout, no RECRUIT) */
    s16 max_hp;
    s16 pride;
    s8 attack_rank;
    s32 money;
    const char *name;     /* full-width UTF-8, like the game's own text */
    const NewSlot *outfit;  /* the look in fights and VS mode (persons 51/52 are built from these slots) */
    int outfit_count;
    s16 street_model;     /* the look walking around: the low-poly street model of this preset (CDATA.XAF
                             entry street_model + 7)... */
    s16 street_tex[10];   /* ...with these DATA.XAF textures (g_StreetTextures layout: 3 shared, then skin,
                             face and body, pants, top, hair, -1, 0) */
} NewChar;

/* Eggusz: preset 56's large body and head (light skin, black mustache), preset 89's red leather jacket and
 * black sneakers, preset 89's trousers with the blue denim texture of preset 27, a bald scalp (preset 55).
 * Textures are DATA.XAF ids: `python tools/bdkit.py tex ISO/XAF/DATA.XAF out 3419` shows one. */
static const NewSlot eggusz_outfit[] = {
    { 195, { 1479, 1479, 1304, 1377, 1304, 1377, 676, 988, 1250, -1 } },   /* body (preset 56) */
    { 227, { 5902, -1 } },                                                 /* jeans */
    { 208, { 3419, -1 } },                                                 /* red leather jacket */
    { 84, { 24, 24, 120, 336, 336, -1 } },                                 /* head with a black mustache */
    { 23, { 1650, -1 } },                                                  /* bald */
    { 3, { 166, -1 } },                                                    /* mouth */
    { 5, { 1582, 1582, -1 } },                                             /* eyes */
    { 31, { 1377, -1 } },                                                  /* hands */
    { 32, { 1377, -1 } },
    { 35, { 1870, -1 } },                                                  /* black sneakers */
    { 36, { 1870, -1 } },
};

static const NewChar new_chars[] = {
    { 51, 87, 83, 56, 37, 12, 0, 3000, 200, 1, 1000,
      "\xEF\xBC\xA5\xEF\xBD\x87\xEF\xBD\x87\xEF\xBD\x95\xEF\xBD\x93\xEF\xBD\x9A",   /* Ｅｇｇｕｓｚ */
      eggusz_outfit, sizeof eggusz_outfit / sizeof eggusz_outfit[0],
      -1, { 3561, 4529, 4729, 1629, 7567, 4535, 5236, 1650, -1, 0 } },   /* override off: pauses PCSX2, see the plan */
};
#define NEW_CHAR_COUNT (int)(sizeof new_chars / sizeof new_chars[0])

/* Where they stand: a person entry added to an area's people for some story stages, like the stage layers
 * of the game's own placement data (g_PeoplePlacement). */
typedef struct {
    s16 person;
    s16 area;             /* Area_Current() id: 5 = ABANDONED SUBWAY STATION */
    u16 stages;           /* bit n = story stage n (g_StoryChapter); chapter 2 is stage 6 */
    s16 slot;             /* g_AreaPeople slot 0-6 it takes (used only if that slot is empty) */
    AreaPerson entry;     /* type 1, person id, then the rest of a real entry: here person 128's spot in the
                             subway, which only stage 9 uses */
} NewPlace;

static const NewPlace new_places[] = {
    { 51, 5, 1 << 6, 1, { 1, 51, 839, 67, { -276, 104, 118 }, 366, 571, 0, 0, 0, { 0 } } },
};
#define NEW_PLACE_COUNT (int)(sizeof new_places / sizeof new_places[0])

/* ---- The code ------------------------------------------------------------------------------------------ */

static Preset built[NEW_CHAR_COUNT];   /* @bss: each character's outfit preset, built on first use */
static int built_ok[NEW_CHAR_COUNT];

static const NewChar *by_person(int person)
{
    int i;
    for (i = 0; i < NEW_CHAR_COUNT; i++)
        if (new_chars[i].person == person)
            return &new_chars[i];
    return NULL;
}

/* Write the template into g_PersonDefs (it lives in the program's data, so this lasts until a reboot). */
static void install_templates(void)
{
    int i;
    for (i = 0; i < NEW_CHAR_COUNT; i++) {
        const NewChar *c = &new_chars[i];
        PersonDef *d = &g_PersonDefs[c->person];
        if (d->preset == c->preset)
            continue;
        memcpy(d, &g_PersonDefs[c->base_template], sizeof *d);
        d->preset = c->preset;
        d->class_row = c->class_row;
        d->level = c->level;
        d->unk0F = 50;
        d->kind = c->kind;
        d->max_hp = c->max_hp;
        d->pride = c->pride;
        d->attack_rank = c->attack_rank;
        d->money = c->money;
        memset(d->start_entries, 0, sizeof d->start_entries);   /* no starting weapon */
    }
}

static Preset *preset_of(int n)
{
    int i, s, p;
    for (i = 0; i < NEW_CHAR_COUNT; i++) {
        const NewChar *c = &new_chars[i];
        Preset *b = &built[i];
        if (c->preset != n)
            continue;
        if (!built_ok[i]) {
            memset(b->slots, 0, sizeof b->slots);
            for (s = 0; s < MAX_SLOTS; s++)
                for (p = 0; p < 16; p++)
                    b->slots[s].parts[p] = -1;
            for (s = 0; s < c->outfit_count && s < MAX_SLOTS; s++) {
                b->slots[s].item = c->outfit[s].item;
                for (p = 0; p < 16 && c->outfit[s].parts[p] >= 0; p++)
                    b->slots[s].parts[p] = c->outfit[s].parts[p];
            }
            memcpy(&b->params, &g_PresetData[c->body_preset].params, sizeof b->params);
            b->params.number = 0;
            b->params.boss = 0;
            built_ok[i] = 1;
        }
        return b;
    }
    return NULL;
}

const char *NC_TextGet(int text_id, int zero)
{
    const NewChar *c = by_person(text_id - TEXT_PERSON_NAME);
    if (c)
        return c->name;
    return orig_Text_Get(text_id, zero);
}

/* Replaces Preset_Get (80 bytes, starts with a branch, so it can't take a @hook): the same lookup in
 * g_PresetData, plus the new presets. Call-site hooks on it (the Aaron cheats, the roster) still work. */
void *NC_PresetGet(int preset, int part)
{
    Preset *b = preset_of(preset);
    if (!b)
        b = &g_PresetData[preset];
    if (part == PRESET_PART_PARAMS)
        return &b->params;
    if (part == PRESET_PART_SLOTS)
        return b;
    return NULL;
}

void NC_PersonInit(int slot, int person_def, int temp)
{
    install_templates();
    orig_Person_Init(slot, person_def, temp);
}

/* Street model: the spawn step 1 (g_NpcSpawnState 1) picks the model and textures from the person's preset;
 * the load starts in step 2, so they can be replaced in between. */
int NC_NpcSpawnStep(int phase, s16 *request)
{
    int state = g_NpcSpawnState;
    int r = orig_NpcSpawn_Step(phase, request);
    const NewChar *c;
    int i;
    if (phase != 0 && state == 1 && (c = by_person(request[1])) != NULL && c->street_model >= 0) {
        g_NpcSpawnModel = c->street_model + 7;
        for (i = 0; i < 10; i++)
            g_NpcSpawnTextures[i] = c->street_tex[i];
    }
    return r;
}

static int in_party(int person)
{
    return person == g_Party[0] || person == g_Party[1] || person == g_Party[2];
}

void *NC_BuildPeople(void)
{
    void *r = orig_Area_BuildPeople();
    int area = Area_Current();
    int stage = g_StoryChapter;
    int i, n;

    for (i = 0; i < NEW_PLACE_COUNT; i++) {
        const NewPlace *pl = &new_places[i];
        Person *p;
        if (pl->area != area || stage < 0 || stage > 15 || !(pl->stages & (1 << stage)))
            continue;
        if (g_AreaPeople[pl->slot].type != 0)
            continue;
        /* A save made before the mod has the old placeholder record: build the person from the template. */
        p = Person_Get(pl->person);
        if (p->preset != by_person(pl->person)->preset) {
            install_templates();
            Person_Init(pl->person, pl->person, 0);
            p = Person_Get(pl->person);
        }
        /* The game's own checks for a person entry (Area_PeopleLayer). */
        if (!Person_IsPresent(pl->person) || p->hp <= 0 || in_party(pl->person) || (p->ally_flags & 1))
            continue;
        g_AreaPeople[pl->slot] = pl->entry;
    }
    for (i = 0, n = 0; i < 7; i++)
        if (g_AreaPeople[i].type == 1)
            n++;
    g_AreaPeopleCount = n;
    return r;
}

// @section New characters: Eggusz (person 51) in the subway, chapter 2
// @description Adds brand-new characters to story mode (docs/mods/PLAN-new-characters.md). Eggusz (person and template 51, a slot left over from a cut character editor): bald, black mustache, red leather jacket, jeans, black sneakers; Jason G's fighting style; level 12, 3000 HP, Pride 200, attack x1.0, $1000. He stands around in the ABANDONED SUBWAY STATION (area 5) during chapter 2 (story stage 6) like any street person: walk up, fight him, RECRUIT him. Everything about a character is one row of the tables in mods/c/new_characters.c.
// @org 0x000A1000
// @max 0x2000
// @bss 0x000E1000 0xC00
// @hook Text_Get NC_TextGet
// @jump Preset_Get NC_PresetGet
// @hook Person_Init NC_PersonInit
// @hook Area_BuildPeople NC_BuildPeople
// @hook NpcSpawn_Step NC_NpcSpawnStep
//
// B.LIST (pause menu blacklist): the game's list g_BList (0x006614A0) has room for 110 people. It moves to
// BL_LIST (0x000E1C00, 200 + 1 entries); the builder and the three helpers that know its size are replaced,
// and every other reference to it is pointed at the new place (`python tools/codemap.py addr-refs
// ISO/SLUS_211.50 6614A0 661580 --move E1C00` prints these lines; the replaced functions' own are left out).
// @jump BList_Build NC_BListBuild
// @jump BList_Clear NC_BListClear
// @jump BList_GetList NC_BListGetList
// @jump BList_IndexOf NC_BListIndexOf
// @word 0x00188074 0x3C02000E   BList_Main+0x1BC (lui)
// @word 0x0018807C 0x24421C00   BList_Main+0x1BC
// @word 0x001881DC 0x3C04000E   BList_Main+0x334 (lui)
// @word 0x001881F4 0x24841C00   BList_Main+0x334
// @word 0x0018831C 0x3C04000E   BList_Main+0x474 (lui)
// @word 0x00188334 0x24841C00   BList_Main+0x474
// @word 0x001886F4 0x3C02000E   BList_Open+0x31C (lui)
// @word 0x001886FC 0x24421C00   BList_Open+0x31C
// @word 0x00188860 0x3C03000E   BList_Open+0x488 (lui)
// @word 0x00188868 0x24631C00   BList_Open+0x488
// @word 0x001889F0 0x3C02000E   BList_Open+0x614 (lui)
// @word 0x001889F4 0x24421C00   BList_Open+0x614
// @word 0x001893D0 0x3C03000E   BList_Open+0xFFC (lui)
// @word 0x001893DC 0x24631C00   BList_Open+0xFFC
// @word 0x00189560 0x3C02000E   BList_Open+0x1188 (lui)
// @word 0x00189568 0x24421C00   BList_Open+0x1188
// @word 0x0018A4B8 0x3C02000E   BList_Input+0xD0 (lui)
// @word 0x0018A4C0 0x24421C00   BList_Input+0xD0
// @word 0x0018A6C0 0x3C02000E   BList_Input+0x2D8 (lui)
// @word 0x0018A6C8 0x24421C00   BList_Input+0x2D8
// @word 0x0018A7D4 0x3C02000E   BList_Input+0x3EC (lui)
// @word 0x0018A7DC 0x24421C00   BList_Input+0x3EC
// @word 0x0018A9D0 0x3C02000E   BList_Input+0x5E8 (lui)
// @word 0x0018A9D8 0x24421C00   BList_Input+0x5E8
// @word 0x0018B408 0x3C02000E   BList_Input+0x101C (lui)
// @word 0x0018B40C 0x24421C00   BList_Input+0x101C
// @word 0x0018B46C 0x3C02000E   BList_Input+0x1084 (lui)
// @word 0x0018B474 0x24421C00   BList_Input+0x1084
// @word 0x0018B4A8 0x3C02000E   BList_Input+0x10C0 (lui)
// @word 0x0018B4B0 0x24421C00   BList_Input+0x10C0
// @word 0x0018B50C 0x3C02000E   BList_Input+0x1124 (lui)
// @word 0x0018B514 0x24421C00   BList_Input+0x1124
// @word 0x0018B598 0x3C04000E   BList_Input+0x11B0 (lui)
// @word 0x0018B5A0 0x24841C00   BList_Input+0x11B0
// @word 0x0018B6F0 0x3C02000E   BList_Input+0x1308 (lui)
// @word 0x0018B6F8 0x24421C00   BList_Input+0x1308
// @word 0x0018B890 0x3C02000E   BList_Input+0x14A8 (lui)
// @word 0x0018B898 0x24421C00   BList_Input+0x14A8
// @word 0x0018BC88 0x3C03000E   BList_DrawRows+0x64 (lui)
// @word 0x0018BC94 0x24631C00   BList_DrawRows+0x64
// @word 0x0018BE18 0x3C02000E   BList_DrawRows+0x1F0 (lui)
// @word 0x0018BE20 0x24421C00   BList_DrawRows+0x1F0
// @word 0x0018CB94 0x3C02000E   BList_HideRows+0x48 (lui)
// @word 0x0018CB98 0x24421C00   BList_HideRows+0x48
// @word 0x0018CD34 0x3C02000E   BList_HideRows+0x1E8 (lui)
// @word 0x0018CD38 0x24421C00   BList_HideRows+0x1E8
// @word 0x0018D048 0x3C02000E   BList_EntryName+0x30 (lui)
// @word 0x0018D050 0x24421C00   BList_EntryName+0x30
// @word 0x0018D204 0x3C02000E   BList_EntryIsAlly+0x18 (lui)
// @word 0x0018D208 0x24421C00   BList_EntryIsAlly+0x18
// @word 0x0018ECCC 0x3C09000E   BList_SetList+0x54 (lui)
// @word 0x0018ECD4 0x25291C00   BList_SetList+0x54
// @word 0x0018ED50 0x3C05000E   BList_SetList+0xD8 (lui)
// @word 0x0018ED58 0x24A51C00   BList_SetList+0xD8
// @word 0x0018ED98 0x3C03000E   BList_SetList+0x11C (lui)
// @word 0x0018ED9C 0x24631C00   BList_SetList+0x11C
//
// VS CUSTOM (fighters from the story saves) lists every template with a blacklist number, so new characters
// are in it through the B.LIST changes above, once their blacklist bit is set (beating them in story mode).
// (g_VsRoster is only read by the old CHARACTER SELECT, VsMode_Main state 8, so nothing is added there.)
// @jump VsCustom_SetupLists NC_VsSetupLists
// @hook Fighter_UsesPresetModel NC_UsesPresetModel
// VS CUSTOM copies P1's player record into person 51 right after loading P1's save; the new characters' own
// records are kept (VS_SAVED) when a save is unpacked and put back while the fighters are made.
// @hook SaveData_Unpack NC_SaveDataUnpack
// @hook VsMode_MakeFighters NC_VsMakeFighters
// VS CUSTOM marks each side's own story hero in its picks as 0x33 / 0x34, which are persons 51 and 52, the new
// characters' slots. The marks become 0x10033 / 0x10034 (the low half is unchanged, and Person_Get only uses
// the low half), and VsMode_MakeFighters tests for those, so a picked person 51 or 52 is the character:
// VsMode_Main's mark loop: lui v1,1; ori a0,v1,0x33 (was li v1,52; li a0,51); ori v1,v1,0x34 (a delay slot nop)
// @word 0x00341DB0 0x3C030001
// @word 0x00341DB4 0x34640033
// @word 0x00341DF0 0x34630034
// VsMode_MakeFighters, P1: lui v0,1 (delay slot nop); ori v0,v0,0x33 (was li v0,51)
// @word 0x003445DC 0x3C020001
// @word 0x003445E0 0x34420033
// P2: VsMode_MirrorId gets and returns the whole id (move a0,v1; move v1,v0; nop instead of the 16-bit
// sign extensions; VS NORMAL ids are small, so nothing changes there), then lui v0,1; ori v0,v0,0x34
// @word 0x00344790 0x0060202D
// @word 0x00344794 0x0040182D
// @word 0x0034479C 0x00000000
// @word 0x003447B0 0x3C020001
// @word 0x003447B8 0x34420034

#include "game.h"

const char *orig_Text_Get(int text_id, int zero);
void orig_Person_Init(int slot, int person_def, int temp);
void *orig_Area_BuildPeople(void);
int orig_NpcSpawn_Step(int phase, s16 *request);
int orig_Fighter_UsesPresetModel(Fighter *fighter);
void orig_SaveData_Unpack(void *buf);
void orig_VsMode_MakeFighters(void);

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
    s16 street_model;     /* the look walking around: this preset's street pack (CDATA.XAF street_model + 7,
                             mesh and 8 textures; -1 = keep the preset's own)... */
    s16 street_tex[10];   /* ...with these DATA.XAF textures instead of the pack's (g_StreetTextures layout:
                             3 shared, skin, face and body, pants, top, hair, -1, 0) */
    s16 blacklist_no;     /* place in the pause menu's B.LIST: the game's people use 1-110, new characters take
                             111, 112, ... in order (no gaps: an empty place would show person 0); 0 = not listed */
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
      89, { 3561, 4529, 4729, 1629, 7567, 4535, 5236, 1650, -1, 0 }, 111 },
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
    int i, j;
    for (i = 0; i < NEW_CHAR_COUNT; i++) {
        const NewChar *c = &new_chars[i];
        PersonDef *d = &g_PersonDefs[c->person];
        if (d->preset == c->preset) {
            d->blacklist_no = c->blacklist_no;   /* also when installed by an older version of this mod */
            continue;
        }
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
        d->blacklist_no = c->blacklist_no;   /* B.LIST place (the list code below takes any number) */
        memset(d->start_entries, 0, sizeof d->start_entries);   /* no starting weapon */
        /* The street model's textures: NpcSpawn_Step copies them per spawn, but 0x002F7290 (head and hair)
         * reads g_StreetTextures[preset] itself, so the new preset's row is written too. */
        if (c->street_model >= 0)
            for (j = 0; j < 10; j++)
                g_StreetTextures[c->preset * 10 + j] = c->street_tex[j];
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

/* Street look. Walking around, a person is the CDATA.XAF pack preset + 7: 8 texture chunks and a mesh. Pack_Load
 * takes each chunk's cache key from g_NpcSpawnTextures (copied from g_StreetTextures[preset]) and reuses a
 * texture already loaded under that key instead of the chunk's pixels. So the new look is: the pack of
 * street_model (its mesh and the textures we keep), plus our DATA.XAF textures loaded first under their own
 * ids (same keys), which the pack load then picks up. NpcSpawn_Step is held in its step 1 until they are in. */
#define MAX_PRELOAD 8
static void *preload_tex[MAX_PRELOAD];   /* @bss */
static int preload_slot, preload_busy, preload_n, preload_i, preload_person;

/* Load the character's street textures that differ from street_model's pack; 1 when all are in. */
static int preload(const NewChar *c)
{
    if (preload_person != c->person) {
        preload_person = c->person;
        preload_n = preload_i = preload_busy = 0;
    }
    for (; preload_i < 8; preload_i++) {
        int id = c->street_tex[preload_i];
        void *t;
        if (id == g_StreetTextures[c->street_model * 10 + preload_i] || preload_n >= MAX_PRELOAD)
            continue;                     /* the pack's own texture */
        if (!preload_busy) {
            t = Tex_Request(0, id, &preload_slot, 1);
            if (t) {
                preload_tex[preload_n++] = t;
                continue;
            }
            preload_busy = 1;
        }
        Xaf_Service();
        t = Tex_Collect(preload_slot);
        if (!t)
            return 0;
        preload_tex[preload_n++] = t;
        preload_busy = 0;
    }
    return 1;
}

static void preload_done(void)
{
    int i;
    for (i = 0; i < preload_n; i++)
        if (preload_tex[i])
            Tex_Release(preload_tex[i]);   /* the spawned person keeps its own reference */
    preload_n = 0;
    preload_person = -1;
}

int NC_NpcSpawnStep(int phase, s16 *request)
{
    const NewChar *c = NULL;
    int state = g_NpcSpawnState, r;
    install_templates();
    if (phase != 0 && (state == 1 || state == 2)) {
        c = by_person(request[1]);
        if (c && c->street_model < 0)
            c = NULL;
    }
    if (c && state == 1 && !preload(c))
        return 0;                        /* wait for our textures */
    r = orig_NpcSpawn_Step(phase, request);
    if (c && state == 1)
        g_NpcSpawnModel = c->street_model + 7;   /* the pack is queued in step 2 */
    if (c && g_NpcSpawnState == 3)
        preload_done();
    return r;
}

static int in_party(int person)
{
    return person == g_Party[0] || person == g_Party[1] || person == g_Party[2];
}

void *NC_BuildPeople(void)
{
    void *r;
    install_templates();
    r = orig_Area_BuildPeople();
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

/* ---- B.LIST ---------------------------------------------------------------------------------------------- */

/* The pause menu's blacklist. BList_Build fills the list from templates 1-200 by PersonDef.blacklist_no, so
 * it never holds more than 200; the game's list had 110 places. Everything else (scrolling, the "No. n"
 * detail panel, the scroll bar) reads g_BListCount and g_BListMaxTop, which the builder sets. These are the
 * game's functions rewritten for any count; with only the game's people they give the same list. */
#define BL_CAP 200
#define BL_LIST ((s16 *)0x000E1C00)   /* g_BList's new place: BL_CAP entries and a -1 (inside @bss's range) */
#define BL_COPY ((s16 *)0x000E1E00)   /* BList_GetList(1)'s copy (was 0x006613C0) */
#define BL_SIZE ((BL_CAP + 1) * 2)

static s16 bl_tail[BL_CAP];   /* @bss: the entries a sort leaves at the end, in list order */
static u8 bl_key[BL_CAP];     /* @bss: sort keys */

/* Persons the list shows as their other record (the game's own pairs, in BList_Build and BList_EntryName). */
static int bl_other(int id)
{
    switch (id) {
    case 0x58: return 0x6E;
    case 0x52: return 0x6D;
    case 0x51: return 0x6A;
    case 0x12: return 0x3C;
    case 0x0F: return 0x4C;
    case 0x0D: return 0x39;
    case 0x0B: return 0x4A;
    case 0x09: return 0x3F;
    case 0x03: return 0x4B;
    }
    return id;
}

/* The count (the highest place); with fill, also puts each template at its place in BL_LIST. */
static int bl_fill(int fill)
{
    int i, n = 0;
    install_templates();
    for (i = 1; i <= 200; i++) {
        int no = g_PersonDefs[i].blacklist_no;
        if (no <= 0 || no > BL_CAP)
            continue;
        if (fill)
            BL_LIST[no - 1] = i;
        if (no > n)
            n = no;
    }
    return n;
}

static void bl_swap(s16 *l, int k)
{
    s16 t = l[k];
    l[k] = l[k - 1];
    l[k - 1] = t;
}

/* Stable sort by bl_key: the same as the game's buckets put one after another. */
static void bl_sort_keys(s16 *l, int n)
{
    int i, j;
    for (i = 1; i < n; i++) {
        s16 v = l[i];
        u8 k = bl_key[i];
        for (j = i; j > 0 && bl_key[j - 1] > k; j--) {
            l[j] = l[j - 1];
            bl_key[j] = bl_key[j - 1];
        }
        l[j] = v;
        bl_key[j] = k;
    }
}

/* Group sort: the player's hero, allies, then by template kind and blist_group, unknown group last. */
static int bl_group_key(int id, int hero)
{
    Person *p = Person_Get(id);
    const PersonDef *d = &g_PersonDefs[id];
    if (id == hero)
        return 0;
    if (!(p->blist_info & 0x20))
        return 11 * 4;
    if (d->kind == 5)
        return 5 * 4;
    if (d->kind != 0)
        return 6 * 4;
    if ((p->ally_flags & 1) == 1) {   /* allies: state 3 first, then in hospital, arrested, the rest */
        if (Person_IsState3(id))
            return 1 * 4 + 0;
        if (p->status & 2)
            return 1 * 4 + 1;
        if (p->status & 8)
            return 1 * 4 + 2;
        return 1 * 4 + 3;
    }
    switch ((s8)d->blist_group) {
    case 1: return 2 * 4;
    case 3: return 3 * 4;
    case 4: return 4 * 4;
    case 6: return 7 * 4;
    case 7: return 8 * 4;
    case 8: return 9 * 4;
    }
    return 10 * 4;
}

/* Skill sort: by the first skill bit found, unknown skills last. */
static int bl_skill_key(int id)
{
    Person *p = Person_Get(id);
    u32 s = p->skills;
    if (!(p->blist_info & 8))
        return 6;
    if (s & 4)
        return 0;
    if (s & 8)
        return 1;
    if (s & 2)
        return 2;
    if (s & 0x3E0)
        return 3;
    if (s & 0x10)
        return 4;
    return 5;
}

/* Replaces BList_Build. sort: 0 group, 1 skills, 2 name, anything else level only (VS mode passes 3). */
void NC_BListBuild(s16 sort)
{
    s16 *l = BL_LIST;
    int n, i, k, tails, hero, selected;
    char a[128], b[128];

    selected = l[g_BListRow + g_BListTop];
    g_BListRow = g_BListTop = 0;
    memset(l, 0, BL_SIZE);
    n = bl_fill(1);
    l[n] = -1;
    g_BListCount = n;

    /* Level order: people whose level is known (blist_info 0x200) first, highest level first, then the rest in
     * place order. People with ally_flags bit 1 get everything shown; the others are shown as their other
     * record. */
    tails = 0;
    for (i = 0; i < n; i++) {
        Person *p = Person_Get(l[i]);
        int level;
        if (!(p->ally_flags & 2))
            l[i] = bl_other(l[i]);
        else
            p->blist_info = 0xFFFF;
        p = Person_Get(l[i]);
        if (!(p->blist_info & 0x200)) {
            bl_tail[tails++] = l[i];
            continue;
        }
        level = p->level;
        for (k = i; k > 0; k--) {
            Person *q = Person_Get(l[k - 1]);
            if (q->level >= level && (q->blist_info & 0x200))
                break;
            bl_swap(l, k);
        }
    }
    if (tails > 0)
        memcpy(&l[n - tails], bl_tail, tails * 2);

    hero = Fighter_HeroId(&g_Fighters[FIGHTER_PLAYER]);
    if (sort == 0 || sort == 1) {
        for (i = 0; i < n; i++)
            bl_key[i] = sort == 0 ? bl_group_key(l[i], hero) : bl_skill_key(l[i]);
        bl_sort_keys(l, n);
    } else if (sort == 2) {
        /* By name (known names, blist_info 0x1000), the rest at the end: the game's insertion sort as is. */
        tails = 0;
        for (i = 0; i < n; i++) {
            if (!(Person_Get(l[i])->blist_info & 0x1000)) {
                bl_tail[tails++] = l[i];
                continue;
            }
            Text_ToAscii(Fighter_DisplayName(l[i]), a);
            for (k = i; k > 0; k--) {
                int c;
                Text_ToAscii(Fighter_DisplayName(l[k - 1]), b);
                c = Str_CompareBytes(a, b);
                if (c != 0 && c != -1 && (Person_Get(l[k - 1])->blist_info & 0x1000))
                    break;
                bl_swap(l, k);
            }
        }
        if (tails > 0)
            memcpy(&l[n - tails], bl_tail, tails * 2);
    }

    g_BListMaxTop = n - 11;
    for (i = 0; i < n; i++)
        if ((Person_Get(l[i])->ally_flags & 1) != 1)
            l[i] = bl_other(l[i]);
    for (i = 0; i < n; i++)
        if (l[i] == selected) {   /* keep the cursor on the person it was on */
            if (i > g_BListMaxTop) {
                g_BListRow = i - (g_BListMaxTop + 1);
                g_BListTop = g_BListMaxTop + 1;
            } else {
                g_BListRow = 0;
                g_BListTop = i;
            }
            break;
        }
    g_BListSort = sort;
}

/* Replaces BList_Clear (VS mode, before it builds the list). */
void NC_BListClear(void)
{
    memset(BL_LIST, 0, BL_SIZE);
    BL_LIST[bl_fill(0)] = -1;
}

/* Replaces BList_GetList: 0 = the list, 1 = a copy of it (VS mode keeps one per side). */
s16 *NC_BListGetList(s16 which)
{
    if (which == 1) {
        memcpy(BL_COPY, BL_LIST, BL_SIZE);
        return BL_COPY;
    }
    return BL_LIST;
}

/* Replaces BList_IndexOf: the index of person in list which, -1 if the list ends first. */
s16 NC_BListIndexOf(s16 which, s16 person)
{
    const s16 *l = which == 1 ? BL_COPY : BL_LIST;
    int i;
    for (i = 0; i < BL_CAP; i++) {
        if (l[i] == person)
            return i;
        if (l[i] == -1)
            return -1;
    }
    return i;
}

/* ---- VS mode --------------------------------------------------------------------------------------------- */

/* Replaces VsCustom_SetupLists: one list per side, with that side's own story hero (g_VsSaveHero) moved to the
 * front, then all its allies (ally_flags bit 0, in that side's save) right after it; +0x5A counts hero + allies,
 * and RANDOM picks among those first entries. The same as the game's, but over the list's length (+0x58)
 * instead of 110. */
static int vs_ally(int side, int id)
{
    return (side == 0 ? Person_Get(id) : Person_GetP2(id))->ally_flags & 1;
}

void NC_VsSetupLists(void)
{
    u8 *vs = g_VsSelect;
    int n = *(s16 *)(vs + 0x58), side, i, j;
    BList_SetList(g_VsCustomIds, n);
    ((s16 **)vs)[0] = BList_GetList(0);
    ((s16 **)vs)[1] = BList_GetList(1);
    if (n > BL_CAP)
        n = BL_CAP;
    for (side = 0; side < 2; side++) {
        s16 *l = ((s16 **)vs)[side];
        s16 *allies = (s16 *)(vs + 0x5A + side * 2);
        *allies = 1;
        for (i = 0; i < n; i++) {
            if (i > 0 && vs_ally(side, l[i])) {
                (*allies)++;
                continue;
            }
            for (j = i; j < n; j++) {
                s16 t;
                if (i == 0 && g_VsSaveHero[side] == (u16)l[j]) {
                    t = l[0];
                    l[0] = l[j];
                    l[j] = t;
                    break;
                }
                if (i > 0 && vs_ally(side, l[j])) {
                    t = l[i];
                    l[i] = l[j];
                    l[j] = t;
                    (*allies)++;
                    break;
                }
            }
        }
    }
}

/* Fight model: the prebuilt ARCHIVE.XAF model of a new character's preset doesn't exist, so his model is always
 * built from the outfit slots (persons 51/52 already are; this covers the copies VS mode fights with). */
int NC_UsesPresetModel(Fighter *fighter)
{
    int i, preset = Person_Get((s16)fighter->person)->preset;
    for (i = 0; i < NEW_CHAR_COUNT; i++)
        if (new_chars[i].preset == preset)
            return 0;
    return orig_Fighter_UsesPresetModel(fighter);
}

/* VS CUSTOM: after loading P1's save, VsMode_Main copies the player record into person 51 (the cut editor's
 * "edit1p", used for the hero in custom clothes), so a picked person 51 would fight as the player's hero. Each
 * new character's record is kept when a save is unpacked and swapped back in while the fighters are made
 * (the hero itself is copied from person 0 then). P2's fighters come from its own save buffer: not affected. */
#define VS_SAVED ((Person *)0x000E2000)   /* NEW_CHAR_COUNT records, fixed address after @bss's range */
static int vs_saved[NEW_CHAR_COUNT];      /* @bss: 1 = VS_SAVED[i] holds the character's record */

void NC_SaveDataUnpack(void *buf)
{
    int i;
    orig_SaveData_Unpack(buf);
    for (i = 0; i < NEW_CHAR_COUNT; i++) {
        Person *p = Person_Get(new_chars[i].person);
        vs_saved[i] = p->preset == new_chars[i].preset;
        if (vs_saved[i])
            memcpy(&VS_SAVED[i], p, sizeof *p);
    }
}

static void vs_swap_saved(void)
{
    int i, k;
    for (i = 0; i < NEW_CHAR_COUNT; i++) {
        u32 *a, *b;
        if (!vs_saved[i])
            continue;
        a = (u32 *)Person_Get(new_chars[i].person);
        b = (u32 *)&VS_SAVED[i];
        for (k = 0; k < (int)(sizeof(Person) / 4); k++) {
            u32 t = a[k];
            a[k] = b[k];
            b[k] = t;
        }
    }
}

void NC_VsMakeFighters(void)
{
    if (!g_VsCustom) {
        orig_VsMode_MakeFighters();
        return;
    }
    vs_swap_saved();
    orig_VsMode_MakeFighters();
    vs_swap_saved();
}

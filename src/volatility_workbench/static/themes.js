/* Original, offline theme artwork. Palette tokens and the catalog are shared by
 * Workbench and Settings. All packaged illustrations are original local compositions;
 * references name the inspiration, and do not load franchise or remote assets. */
(() => {
  'use strict';
  const key = 'volatility-workbench-theme';
  const defaultTheme = 'matrix';
  // Dark, opaque work surfaces keep decoration out of forensic content. Each
  // tuple is background, panel, control, border, text, muted, accent, on-accent.
  const catalog = [
    ['matrix','Matrix green','Classic','#0d1418 #141f25 #0c171c #526d70 #e5eeee #9fb2bb #9cddb7 #102219','Classic charcoal and phosphor green.','plain'],
    ['halloween','Halloween · pumpkin night','Seasonal','#05060b #13121c #151620 #73637c #f8eee3 #c5b8c9 #ffc17b #2b190d','A friendly moonlit pumpkin patch.','rounded'],
    ['halloween-noir','Halloween · midnight orchard','Seasonal','#0d0b0b #1b1616 #211b1a #7e675c #f5e8db #c9b6aa #eebc8c #29180e','Bare branches, harvest light and autumn mist.','serif'],
    ['nightmare','The Nightmare Before Christmas','Seasonal','#100f18 #1d1929 #231e30 #786984 #f4eee4 #c5b8d2 #dbc69a #241c2c','A curled hill and a moonlit, crooked silhouette.','serif'],
    ['fallout','Fallout (1997)','Fallout','#151613 #20231d #25291f #77775b #efeacb #c4c5a5 #d1c991 #272816','Weathered vault steel and a desert horizon.','terminal'],
    ['fallout-2','Fallout 2','Fallout','#10140e #151c12 #24291c #8d9171 #c3e9b4 #a8b896 #83ff35 #15210c','Riveted olive steel, worn brass controls and recessed phosphor screens.','terminal'],
    ['fallout-tactics','Fallout Tactics: Brotherhood of Steel','Fallout','#0c1717 #192929 #1d3030 #568077 #e3efdf #b1c9c1 #a8d4b9 #11291d','A tactical grid with connected squad markers.','terminal'],
    ['fallout-brotherhood','Fallout: Brotherhood of Steel','Fallout','#191213 #2b1e20 #302326 #8c6e67 #f4e6d6 #ceb7aa #e3b394 #321b13','Steel heraldry and a weathered crimson field.','industrial'],
    ['fallout-3','Fallout 3','Fallout','#10170e #1b2818 #20301b #698059 #e7efd5 #bbcbab #b6d695 #203016','A green wasteland and a broken capital skyline.','terminal'],
    ['fallout-new-vegas','Fallout: New Vegas','Fallout','#1b1117 #2d2028 #35242a #966c64 #ffebd2 #d9b9ae #ffc28c #341e13','Weathered cream and rust, neon marquee bulbs and desert dusk.','industrial'],
    ['fallout-4','Fallout 4','Fallout','#0e1b20 #1a2b30 #1d333a #588389 #e4f2ed #b2ceca #a8dfd6 #173130','Coastal blue steel and a suspension bridge.','industrial'],
    ['fallout-shelter','Fallout Shelter','Fallout','#17180f #252b1b #2d3420 #788459 #f2eed2 #c6c9a2 #e8ce88 #30270f','A warm cross-section of a busy underground vault.','rounded'],
    ['fallout-76','Fallout 76','Fallout','#0d1d21 #1a3035 #203b40 #62898a #e9f4e9 #bdd2c6 #e6ce92 #2a2814','Appalachian pines, blue steel and a golden 76.','industrial'],
    ['fallout-4-vr','Fallout 4 VR','Fallout','#0d1922 #1b2c39 #203544 #61859a #edf1ec #bdcdd4 #bfdde6 #1b2a33','A steel-blue headset framing twin wasteland horizons.','industrial'],
    ['fallout-pinball','Fallout Pinball','Fallout','#1a1422 #2e233a #352940 #857198 #f8ecdf #cbbdd1 #dfc599 #322414','A vault-inspired playfield, warm bumpers and paired flippers.','rounded'],
    ['fallout-shelter-online','Fallout Shelter Online','Fallout','#0b1927 #162d41 #1b364c #6286a1 #e9f1f2 #b6cbd8 #e8ce8e #282315','Connected vault rooms in bright blue and gold.','rounded'],
    ['8-bit','8-bit · bonus stage','Arcade & adventure','#101228 #1e2140 #26294a #6e73a8 #f1edff #bebde1 #ffda85 #2d2510','Pixel platforms and a tiny visitor from the arcade.','pixel'],
    ['adventure','Colossal Cave Adventure','Arcade & adventure','#0d1719 #1a292a #213334 #66827c #edf0d9 #bbcdbd #e6cf96 #282515','A lamp, a treasure chest and the entrance to a cavern.','terminal'],
    ['metroid','Metroid','Arcade & adventure','#091a20 #152d34 #1c3740 #558982 #e7f3e3 #b2d0c6 #eec489 #322211','Alien caverns, an amber explorer and a floating organism.','industrial'],
    ['silpheed','Silpheed · Sega CD','Arcade & adventure','#0c1327 #172540 #1e2e4e #5f7ca6 #edf1ff #b9c8e2 #b9d9ff #142841','A faceted starfighter over a polygonal space grid.','industrial'],
    ['elevator','Elevator Action · NES','Arcade & adventure','#101b24 #1f303e #283a4b #8784a5 #f2f0da #bfcbd1 #cab5e6 #282137','Teal office walls, purple doors and stacked elevator shafts.','pixel'],
    ['vaporwave','Vaporwave · marble sunset','Neon & terminals','#191329 #2c2240 #34294b #8c6fa2 #fff0f8 #d4b8dc #f2b9d1 #3a2037','Pastel marble, a striped sun and an endless lavender grid.','serif'],
    ['retrowave','Retrowave · night drive','Neon & terminals','#120e23 #241b37 #2d2142 #92659c #fce9fb #d3b2d1 #f3abd4 #32162c','A neon road, low silhouette and a coral sunset.','industrial'],
    ['hacker','Hacker · secure terminal','Neon & terminals','#0a151c #152731 #1a303b #51808c #e4f0ef #aecbd0 #9cddc5 #112c25','A quiet terminal, amber lock and cyan instrument lines.','terminal'],
    ['top-gun','Top Gun','Cinema & anime','#111b26 #1e2d3b #253646 #688396 #f1f0e7 #c1ced1 #e9bd99 #2e2118','Swept wings, a carrier horizon and warm flight-deck light.','industrial'],
    ['oedo','Cyber City Oedo 808','Cinema & anime','#121322 #22223b #2b2c46 #7579a0 #f7e9ed #c4bfd7 #ecb0b4 #331e30','Rain over a dense skyline, analog cyan and warm red neon.','industrial'],
    ['cyberpunk','Cyberpunk 2077','Cinema & anime','#111c21 #1c2e35 #243942 #6a878e #f4f4d6 #c2d0c5 #ede785 #282910','A vertical city cut by yellow traces and electric pink signs.','industrial'],
    ['golgo','Golgo 13','Cinema & anime','#10131c #202532 #272e3e #737990 #f1ece7 #c5c3c8 #e7acac #301a21','A still silhouette, distant sightlines and a crimson sun.','serif'],
    ['punisher','The Punisher · War Journal #53','Cinema & anime','#13151e #242937 #2c3344 #798197 #f3edeb #c5c7d2 #e3b0b7 #341c28','Coral action streaks, navy armor and wire, after the 1993 cover.','industrial'],
    ['mono','Soft black and white','Classic','#08090a #121416 #101214 #62666c #e2e3e4 #b5b8bc #d1d3d5 #0b0c0d','Quiet geometry in soft charcoal and silver.','plain'],
    ['blue','Light blue','Classic','#0b1620 #142431 #0d1d28 #567a91 #e2f0f5 #afc9d6 #9bdcf3 #0d2532','Soft blue waveforms on a cool dark work surface.','plain'],
  ];
  const tokens = ['bg','panel','control-bg','border','text','muted','accent','accent-text'];
  const themes = new Map(catalog.map(([id,label,group,palette,description,shape]) => [id,{id,label,group,palette,description,shape}]));
  let connected=false, revision=-1, selection=0, pending=null, saves=Promise.resolve();
  function cache(id) { try {localStorage.setItem(key,id);} catch {} }
  function saveMessage(text, retry=false) {
    document.querySelectorAll('[data-theme-picker]').forEach(select=>{
      let status=select.parentElement.querySelector('[data-theme-save-status]');
      if(!status){status=document.createElement('span');status.dataset.themeSaveStatus='';status.className='subtle';status.setAttribute('role','status');status.setAttribute('aria-live','polite');select.after(status);}
      status.textContent=text;status.hidden=!text;
      let button=select.parentElement.querySelector('[data-theme-save-retry]');
      if(!button){
        button=document.createElement('button');button.type='button';button.dataset.themeSaveRetry='';button.textContent='Retry save';status.after(button);
        button.addEventListener('click',()=>{if(pending&&connected){saveMessage('Saving theme…');save(pending,selection);}});
      }
      button.hidden=!retry;
    });
  }
  function save(id, chosen, migrate=false) {
    saves=saves.then(async()=>{
      // Coalesce rapid selections that have not been sent yet.
      if(chosen!==selection)return;
      saveMessage('Saving theme…');
      try {
        const body=migrate?{theme:id,expected_revision:0}:{theme:id};
        const response=await fetch('/api/settings/appearance',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(body)});
        const result=await response.json();
        if(!response.ok||result.schema!=='appearance/1'||!themes.has(result.theme)||(!migrate&&result.theme!==id)||!Number.isSafeInteger(result.revision)||result.revision<1)throw Error('Theme preference save failed');
        revision=Math.max(revision,result.revision);
        if(chosen===selection){pending=null;if(migrate){apply(result.theme);cache(result.theme);}saveMessage('');}
      } catch {
        if(chosen===selection)saveMessage('Theme changed in this window, but could not be saved for the next launch.',true);
      }
    });
  }
  function sync(appearance) {
    // Existing local preferences are a migration/fallback cache. The authenticated
    // server preference is authoritative across dynamic loopback origins.
    if(!appearance||appearance.schema!=='appearance/1'||!Number.isSafeInteger(appearance.revision)||appearance.revision<0)return;
    const first=!connected;connected=true;
    if(pending){if(first)save(pending,selection);return;}
    if(appearance.revision<=revision)return;
    revision=appearance.revision;
    if(themes.has(appearance.theme)){apply(appearance.theme);cache(appearance.theme);saveMessage('');}
    else if(first){
      const legacy=saved();
      if(themes.has(legacy)&&!appearance.error){pending=legacy;save(legacy,++selection,true);}
      if(appearance.error)saveMessage(appearance.error);
    }
  }
  function apply(value, persist=false) {
    const theme = themes.get(value) || themes.get(defaultTheme);
    const root = document.documentElement;
    root.dataset.theme = theme.id;
    root.dataset.themeShape = theme.shape;
    theme.palette.split(' ').forEach((color,i)=>root.style.setProperty('--'+tokens[i],color));
    root.style.setProperty('--theme-scene',theme.id==='halloween-noir' ? 'url("/halloween-night.png")' : `url("/theme-${theme.id}.svg")`);
    const classic = theme.id==='matrix';
    root.style.setProperty('--privacy-bg', classic ? '#1d2a27' : 'var(--panel)');
    root.style.setProperty('--privacy-text', classic ? '#bed9c9' : 'var(--text)');
    root.style.setProperty('--code-bg', classic ? '#091014' : 'var(--bg)');
    root.style.setProperty('--status', classic ? '#e9c889' : '#f3cf93');
    root.style.setProperty('--danger', classic ? '#ffb6a5' : '#ffb6ad');
    root.style.setProperty('--error-border', classic ? '#b46955' : '#d79283');
    root.style.setProperty('--error-text', classic ? '#ffc3b4' : '#ffc7bc');
    root.style.setProperty('--zoom-bg', classic ? '#080d10ed' : '#080d10f5');
    root.style.setProperty('--zoom-text', classic ? '#e6eee9' : '#f0f4ef');
    document.querySelectorAll('[data-theme-picker]').forEach(select=>{ select.value=theme.id; });
    if(persist) {
      cache(theme.id);pending=theme.id;++selection;
      if(connected)save(theme.id,selection);
    }
    return theme.id;
  }
  function saved() { try {return localStorage.getItem(key);} catch {return null;} }
  apply(saved());
  function mount() {
    document.querySelectorAll('[data-theme-picker]').forEach(select=>{
      for(const group of new Set(catalog.map(theme=>theme[2]))) {
        const optgroup=document.createElement('optgroup'); optgroup.label=group;
        for(const theme of themes.values()) if(theme.group===group) {
          const option=document.createElement('option'); option.value=theme.id; option.textContent=theme.label; optgroup.append(option);
        }
        select.append(optgroup);
      }
      select.value=document.documentElement.dataset.theme;
      select.addEventListener('change',()=>apply(select.value,true));
    });
    apply(document.documentElement.dataset.theme);
  }
  window.WorkbenchThemes=Object.freeze({catalog: Object.freeze(Array.from(themes.values()).map(theme=>Object.freeze({...theme}))), apply, sync, defaultTheme});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true}); else mount();
  // Once connected, revisioned server snapshots coordinate both windows. A stale
  // browser cache event must never replace an unsaved or confirmed selection.
  window.addEventListener('storage',event=>{if(!connected&&!pending&&event.key===key)apply(event.newValue);});
})();

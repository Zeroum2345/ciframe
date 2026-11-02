var app = angular
  .module('deciframeApp', ['ngRoute', 'ngAnimate', 'ngProgress', 'ui.bootstrap'])
  .constant('RESTAPI', {
    url: 'http://localhost:5003'
  })
  .constant('GENEROS', [
    "Brega",
    "Gótico",
    "Samba",
    "Emocore",
    "Eletrônica",
    "Psicodelia",
    "Clássico",
    "Gospel/Religioso",
    "Heavy Metal",
    "Instrumental",
    "Reggae",
    "Hard Rock",
    "Pop Rock",
    "Marchas/Hinos",
    "Regional",
    "Romântico",
    "Velha Guarda",
    "Pagode",
    "Jovem Guarda",
    "Rockabilly",
    "Hardcore",
    "Bossa Nova",
    "Punk Rock",
    "Power-Pop",
    "Country",
    "Guarânia",
    "Funk Carioca",
    "Soul",
    "Disco",
    "New Wave",
    "Soft Rock",
    "Rock Progressivo",
    "World Music",
    "Rock",
    "Sertanejo",
    "Grunge",
    "Samba Enredo",
    "Bolero",
    "Industrial",
    "MPB",
    "Hip Hop/Rap",
    "Indie",
    "Surf Music",
    "Infantil",
    "Pop",
    "Alternativo",
    "Forró",
    "Blues",
    "Axé",
    "Jazz",
    "Folk"
    ])
  .constant('PALETA_ACORDES', [
    [
      { 'acorde': 'C',   'cor': '#e6b300' },
      { 'acorde': 'C#',  'cor': '#e6b300' },
      { 'acorde': 'Cm',  'cor': '#efcc59' },
      { 'acorde': 'C#m', 'cor': '#efcc59' },
      { 'acorde': 'C7',  'cor': '#d6a602' },
      { 'acorde': 'C#7', 'cor': '#d6a602' }
    ],
    [
      { 'acorde': 'D',   'cor': '#cb6018' },
      { 'acorde': 'D#',  'cor': '#cb6018' },
      { 'acorde': 'Dm',  'cor': '#cf6f3e' },
      { 'acorde': 'D#m', 'cor': '#cf6f3e' },
      { 'acorde': 'D7',  'cor': '#bc5a1d' },
      { 'acorde': 'D#7', 'cor': '#bc5a1d' }
    ],
    [
      { 'acorde': 'E',  'cor': '#b72c52' },
      { 'acorde': 'Em', 'cor': '#c5516e' },
      { 'acorde': 'E7', 'cor': '#a92f4d' }
    ],
    [
      { 'acorde': 'F',   'cor': '#ba007c' },
      { 'acorde': 'F#',  'cor': '#ba007c' },
      { 'acorde': 'Fm',  'cor': '#c02a88' },
      { 'acorde': 'F#m', 'cor': '#c02a88' },
      { 'acorde': 'F7',  'cor': '#ad0076' },
      { 'acorde': 'F#7', 'cor': '#ad0076' }
    ],
    [
      { 'acorde': 'G',   'cor': '#7b057e' },
      { 'acorde': 'G#',  'cor': '#7b057e' },
      { 'acorde': 'Gm',  'cor': '#882888' },
      { 'acorde': 'G#m', 'cor': '#882888' },
      { 'acorde': 'G7',  'cor': '#710c77' },
      { 'acorde': 'G#7', 'cor': '#710c77' }
    ],
    [
      { 'acorde': 'A',   'cor': '#76aadb' },
      { 'acorde': 'A#',  'cor': '#76aadb' },
      { 'acorde': 'Am',  'cor': '#89c0e9' },
      { 'acorde': 'A#m', 'cor': '#89c0e9' },
      { 'acorde': 'A7',  'cor': '#6c9ecc' },
      { 'acorde': 'A#7', 'cor': '#6c9ecc' }
    ],
    [
      { 'acorde': 'B',  'cor': '#a3bd31' },
      { 'acorde': 'Bm', 'cor': '#cdd54f' },
      { 'acorde': 'B7', 'cor': '#96b02f' }
    ]
  ]);

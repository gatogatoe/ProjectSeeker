'use strict';

const translations = {
  it: {
    skip: 'Vai al contenuto', language: 'Lingua', navExplore: 'Esplora', navDownload: 'Scarica',
    eyebrow: 'PER LE IDEE CHE AVEVI QUASI DIMENTICATO', hero1: 'La tua prossima idea.', hero2: 'È già sul tuo disco.',
    intro: 'Quel beat della scorsa estate. Quella sessione con il suono perfetto. Ritrovala, ascoltala e riparti da dove eri rimasto.',
    getApp: 'Scarica Project Seeker', seeApp: 'Guarda dentro', heroMeta: 'GRATUITO E OPEN SOURCE · FL STUDIO + ABLETON LIVE',
    principle1: 'I tuoi file restano tuoi.', principle2: 'Nessun account. Nessuna pubblicità.', principle3: 'Esplora e ascolta offline.',
    insideLabel: '01 / RITORNA ALLA TUA MUSICA', insideTitle: 'Meno ricerche. Più musica.', insideIntro: 'Un posto per progetti, export audio e idee da finire.',
    previewCaption: 'DENTRO L’APP', viewProjects: 'Progetti', viewMap: 'Bubble map', viewAlbum: 'Album', imageNote: 'Libreria dimostrativa. Clicca sull’immagine per ingrandirla.',
    feature1Title: 'Ritrova la sessione', feature1: 'Cerca per nome, plugin, sample o BPM. Esplora la libreria come elenco o attraverso la Bubble map.',
    feature2Title: 'Ascolta l’idea', feature2: 'Ascolta gli export audio associati senza aprire la DAW. Il player usa i tuoi export; non esegue il rendering dei progetti.',
    feature3Title: 'Riprendi il filo', feature3: 'Raccogli le idee in album e playlist, poi riapri un progetto nella DAW installata. I file originali restano al loro posto.',
    downloadLabel: '02 / LA PROSSIMA SESSIONE INIZIA QUI', downloadTitle: 'Fai spazio alle vecchie idee.', downloadIntro: 'Gratuito. Senza abbonamento. Parti da una cartella di progetti.',
    downloadWindows: 'Scarica per Windows', windowsNote: 'Installazione senza diritti di amministratore. Richiede Microsoft Edge WebView2 Runtime.', installHelp: 'Installazione e SmartScreen →',
    macNote: 'Apri il DMG e trascina l’app in Applicazioni. Questa build Mac usa la licenza MIT.', macHelp: 'Installazione su Mac →',
    macFaqTitle: 'Come installo la versione Mac?', macFaq: 'Scegli Apple Silicon per un Mac con chip della serie M, oppure Intel per un Mac Intel. Apri il DMG e trascina Project Seeker in Applicazioni. L’app non ha una firma Apple Developer ID né la notarizzazione. Se macOS ne blocca l’apertura, verifica provenienza e SHA-256 del download, poi usa Impostazioni di Sistema → Privacy e sicurezza → Apri comunque, se disponibile. I controlli automatici su Mac non sostituiscono una prova sul tuo Mac.',
    sourceTitle: 'Fallo tuo.', sourceMeta: 'Codice dell’app · v0.9', downloadSource: 'Scarica i sorgenti', sourceNote: 'Codice dell’app, test sintetici e script di build. Usa, modifica e condividi secondo la GPL.', readLicense: 'Leggi la licenza →',
    checksumTitle: 'Verifica il download · SHA-256', checksumIntro: 'Confronta lo SHA-256 dell’installer con il valore qui sotto. In PowerShell esegui:', copy: 'Copia', copied: 'SHA-256 copiato.', copyFailed: 'Copia non disponibile: seleziona e copia il valore manualmente.', allChecksums: 'Checksum di tutti i download →',
    helpLabel: '03 / DA SAPERE', helpTitle: 'Dal download\nal primo ascolto.', helpIntro: 'Qualche indicazione prima di cominciare.',
    faq1Title: 'Windows mostra un avviso SmartScreen. Perché?', faq1: 'L’installer non è firmato digitalmente. Windows può mostrare “PC protetto da Windows”: l’avviso da solo non significa che sia stato rilevato un malware. Controlla di aver scaricato dalla pagina del progetto e confronta lo SHA-256 qui sopra. Per proseguire seleziona “Ulteriori informazioni” → “Esegui comunque”, se Windows offre questa opzione.',
    faq2Title: 'Come comincio?', faq2: 'Esegui l’installer, apri Project Seeker e scegli una cartella con progetti .flp o .als. Dopo la scansione cerca nella libreria e seleziona un progetto. Associa un export audio per ascoltarlo, oppure riapri il progetto in FL Studio o Ableton Live.',
    faq3Title: 'Modifica i miei progetti?', faq3: 'La scansione legge i progetti e i sample originali senza spostarli, rinominarli o salvarli. Album, playlist e note restano nei dati dell’app. Reviver, lo strumento facoltativo di recupero, è in beta e disattivato inizialmente.',
    faq4Title: 'Servono un account o un modello AI?', faq4: 'No. Scansione, consultazione e ascolto funzionano offline senza account. L’assistente è facoltativo. Se scegli un provider AI esterno, i messaggi vengono inviati a quel provider; condividere i metadati della libreria richiede un consenso separato.',
    faq5Title: 'Quali lingue sono disponibili?', faq5: 'Project Seeker è disponibile in inglese, italiano, francese e tedesco. Scegli la lingua nelle impostazioni dell’app.',
    closing: 'Hai già creato qualcosa che merita di essere ripreso.', footerSource: 'Codice sorgente', credits: 'Attribuzioni di terzi', licenses: 'Licenze delle dipendenze', trademark: 'FL Studio e Ableton Live sono marchi dei rispettivi proprietari. Nessuna affiliazione o approvazione.'
  },
  fr: {
    skip: 'Aller au contenu', language: 'Langue', navExplore: 'Explorer', navDownload: 'Télécharger',
    eyebrow: 'POUR LES IDÉES PRESQUE OUBLIÉES', hero1: 'Votre prochaine idée.', hero2: 'Déjà sur votre disque.',
    intro: 'Ce beat de l’été dernier. Cette session au son parfait. Retrouvez-la, écoutez-la et reprenez là où vous en étiez.',
    getApp: 'Télécharger Project Seeker', seeApp: 'Découvrir l’app', heroMeta: 'GRATUIT ET OPEN SOURCE · FL STUDIO + ABLETON LIVE',
    principle1: 'Vos fichiers restent les vôtres.', principle2: 'Sans compte. Sans publicité.', principle3: 'Explorez et écoutez hors ligne.',
    insideLabel: '01 / RETROUVEZ VOTRE MUSIQUE', insideTitle: 'Moins chercher. Plus créer.', insideIntro: 'Un seul endroit pour vos projets, exports audio et idées à terminer.',
    previewCaption: 'DANS L’APPLICATION', viewProjects: 'Projets', viewMap: 'Bubble map', viewAlbum: 'Albums', imageNote: 'Bibliothèque de démonstration. Cliquez sur l’image pour l’agrandir.',
    feature1Title: 'Retrouvez la session', feature1: 'Recherchez par nom, plugin, sample ou BPM. Explorez votre bibliothèque en liste ou avec la Bubble map.',
    feature2Title: 'Écoutez l’idée', feature2: 'Écoutez les exports audio associés sans ouvrir votre DAW. Le lecteur utilise vos exports ; il ne produit pas le rendu des projets.',
    feature3Title: 'Gardez votre élan', feature3: 'Rassemblez vos idées en albums et playlists, puis rouvrez un projet dans votre DAW installée. Les fichiers originaux restent en place.',
    downloadLabel: '02 / VOTRE PROCHAINE SESSION COMMENCE ICI', downloadTitle: 'Retrouvez vos anciennes idées.', downloadIntro: 'Gratuit. Sans abonnement. Commencez avec un dossier de projets.',
    downloadWindows: 'Télécharger pour Windows', windowsNote: 'Installation sans droits administrateur. Nécessite Microsoft Edge WebView2 Runtime.', installHelp: 'Installation et SmartScreen →',
    macNote: 'Ouvrez le DMG et glissez l’app dans Applications. Cette version Mac utilise la licence MIT.', macHelp: 'Installation sur Mac →',
    macFaqTitle: 'Comment installer la version Mac ?', macFaq: 'Choisissez Apple Silicon pour un Mac avec une puce de la série M, ou Intel pour un Mac Intel. Ouvrez le DMG et glissez Project Seeker dans Applications. L’app n’a ni signature Apple Developer ID ni notarisation. Si macOS bloque son ouverture, vérifiez la provenance et le SHA-256 du téléchargement, puis utilisez Réglages Système → Confidentialité et sécurité → Ouvrir quand même, si disponible. Les contrôles automatiques sur Mac ne remplacent pas un essai sur votre propre Mac.',
    sourceTitle: 'À vous de jouer.', sourceMeta: 'Code de l’app · v0.9', downloadSource: 'Télécharger les sources', sourceNote: 'Code de l’app, tests synthétiques et scripts de compilation. Utilisez, modifiez et partagez selon la GPL.', readLicense: 'Lire la licence →',
    checksumTitle: 'Vérifier le téléchargement · SHA-256', checksumIntro: 'Comparez le SHA-256 de l’installeur à la valeur ci-dessous. Dans PowerShell, exécutez :', copy: 'Copier', copied: 'SHA-256 copié.', copyFailed: 'Copie indisponible : sélectionnez et copiez la valeur manuellement.', allChecksums: 'Empreintes de tous les téléchargements →',
    helpLabel: '03 / BON À SAVOIR', helpTitle: 'Du téléchargement\nà la première écoute.', helpIntro: 'Quelques indications avant de commencer.',
    faq1Title: 'Pourquoi Windows affiche-t-il un avertissement SmartScreen ?', faq1: 'L’installeur n’est pas signé numériquement. Windows peut afficher « Windows a protégé votre ordinateur » ; cet avertissement seul ne signifie pas qu’un logiciel malveillant a été détecté. Vérifiez la provenance du téléchargement et comparez le SHA-256 ci-dessus. Pour continuer, sélectionnez « Informations complémentaires » → « Exécuter quand même », si Windows propose cette option.',
    faq2Title: 'Comment commencer ?', faq2: 'Lancez l’installeur, ouvrez Project Seeker et choisissez un dossier de projets .flp ou .als. Après l’analyse, recherchez et sélectionnez un projet. Associez un export audio pour l’écouter ou rouvrez le projet dans FL Studio ou Ableton Live.',
    faq3Title: 'L’app modifie-t-elle mes projets ?', faq3: 'L’analyse lit les projets et samples originaux sans les déplacer, les renommer ni les enregistrer. Albums, playlists et notes restent dans les données de l’app. Reviver, l’outil de récupération facultatif, est en bêta et désactivé par défaut.',
    faq4Title: 'Faut-il un compte ou un modèle IA ?', faq4: 'Non. L’analyse, la navigation et l’écoute fonctionnent hors ligne sans compte. L’assistant est facultatif. Si vous choisissez un fournisseur IA externe, vos messages lui sont envoyés ; le partage des métadonnées de la bibliothèque nécessite un consentement distinct.',
    faq5Title: 'Quelles langues sont disponibles ?', faq5: 'Project Seeker est disponible en anglais, italien, français et allemand. Choisissez la langue dans les paramètres de l’app.',
    closing: 'Vous avez déjà créé quelque chose qui mérite une nouvelle écoute.', footerSource: 'Code source', credits: 'Mentions des tiers', licenses: 'Licences des dépendances', trademark: 'FL Studio et Ableton Live sont des marques de leurs propriétaires respectifs. Aucune affiliation ni approbation.'
  },
  de: {
    skip: 'Zum Inhalt', language: 'Sprache', navExplore: 'Entdecken', navDownload: 'Download',
    eyebrow: 'FÜR IDEEN, DIE FAST VERGESSEN WAREN', hero1: 'Deine nächste Idee.', hero2: 'Schon auf deiner Platte.',
    intro: 'Der Beat vom letzten Sommer. Die Session mit dem perfekten Sound. Finde sie wieder, hör rein und mach dort weiter, wo du aufgehört hast.',
    getApp: 'Project Seeker herunterladen', seeApp: 'Ein Blick in die App', heroMeta: 'KOSTENLOS UND OPEN SOURCE · FL STUDIO + ABLETON LIVE',
    principle1: 'Deine Dateien bleiben deine.', principle2: 'Kein Konto. Keine Werbung.', principle3: 'Offline stöbern und hören.',
    insideLabel: '01 / ZURÜCK ZU DEINER MUSIK', insideTitle: 'Weniger suchen. Mehr machen.', insideIntro: 'Ein Ort für Projekte, Audio-Exporte und unfertige Ideen.',
    previewCaption: 'EIN BLICK IN DIE APP', viewProjects: 'Projekte', viewMap: 'Bubble map', viewAlbum: 'Alben', imageNote: 'Demo-Bibliothek. Klicke auf das Bild, um es zu vergrößern.',
    feature1Title: 'Finde die Session', feature1: 'Suche nach Namen, Plugins, Samples oder BPM. Entdecke deine Bibliothek als Liste oder mit der Bubble map.',
    feature2Title: 'Hör dir die Idee an', feature2: 'Höre zugeordnete Audio-Exporte, ohne deine DAW zu öffnen. Der Player nutzt deine Exporte; er rendert keine Projektdateien.',
    feature3Title: 'Bleib im Flow', feature3: 'Sammle Ideen in Alben und Playlists und öffne ein Projekt in deiner installierten DAW. Die Originaldateien bleiben an ihrem Platz.',
    downloadLabel: '02 / DEINE NÄCHSTE SESSION BEGINNT HIER', downloadTitle: 'Platz für alte Ideen.', downloadIntro: 'Kostenlos. Ohne Abo. Starte mit einem Projektordner.',
    downloadWindows: 'Für Windows herunterladen', windowsNote: 'Installation ohne Administratorrechte. Benötigt Microsoft Edge WebView2 Runtime.', installHelp: 'Installation und SmartScreen →',
    macNote: 'Öffne das DMG und ziehe die App in Programme. Dieser Mac-Build verwendet die MIT-Lizenz.', macHelp: 'Installation auf dem Mac →',
    macFaqTitle: 'Wie installiere ich die Mac-Version?', macFaq: 'Wähle Apple Silicon für einen Mac mit einem Chip der M-Serie oder Intel für einen Intel-Mac. Öffne das DMG und ziehe Project Seeker in Programme. Die App besitzt weder eine Apple Developer ID-Signatur noch eine Notarisierung. Falls macOS das Öffnen blockiert, prüfe Herkunft und SHA-256 des Downloads und nutze Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen, falls verfügbar. Automatische Mac-Prüfungen ersetzen keinen Test auf deinem eigenen Mac.',
    sourceTitle: 'Mach es zu deinem.', sourceMeta: 'App-Quellcode · v0.9', downloadSource: 'Quellcode herunterladen', sourceNote: 'App-Code, synthetische Tests und Build-Skripte. Unter der GPL nutzen, ändern und teilen.', readLicense: 'Lizenz lesen →',
    checksumTitle: 'Download prüfen · SHA-256', checksumIntro: 'Vergleiche den SHA-256-Wert des Installers mit dem Wert unten. Führe in PowerShell aus:', copy: 'Kopieren', copied: 'SHA-256 kopiert.', copyFailed: 'Kopieren nicht verfügbar: Wert auswählen und manuell kopieren.', allChecksums: 'Prüfsummen aller Downloads →',
    helpLabel: '03 / GUT ZU WISSEN', helpTitle: 'Vom Download\nzum ersten Anhören.', helpIntro: 'Ein paar Hinweise vor dem Start.',
    faq1Title: 'Warum zeigt Windows eine SmartScreen-Warnung?', faq1: 'Der Installer ist nicht digital signiert. Windows kann „Der Computer wurde durch Windows geschützt“ anzeigen; diese Warnung allein bedeutet nicht, dass Schadsoftware erkannt wurde. Prüfe die Herkunft des Downloads und vergleiche den SHA-256-Wert oben. Wähle zum Fortfahren „Weitere Informationen“ → „Trotzdem ausführen“, falls Windows diese Option anbietet.',
    faq2Title: 'Wie fange ich an?', faq2: 'Führe den Installer aus, öffne Project Seeker und wähle einen Ordner mit .flp- oder .als-Projekten. Suche nach dem Scan in deiner Bibliothek und wähle ein Projekt. Ordne einen Audio-Export zum Anhören zu oder öffne das Projekt in FL Studio oder Ableton Live.',
    faq3Title: 'Werden meine Projekte verändert?', faq3: 'Der Scan liest Originalprojekte und Samples, ohne sie zu verschieben, umzubenennen oder zu speichern. Alben, Playlists und Notizen liegen in den App-Daten. Das optionale Wiederherstellungswerkzeug Reviver ist in der Beta und standardmäßig deaktiviert.',
    faq4Title: 'Brauche ich ein Konto oder ein KI-Modell?', faq4: 'Nein. Scannen, Stöbern und Wiedergabe funktionieren offline ohne Konto. Der Assistent ist optional. Wenn du einen externen KI-Anbieter wählst, gehen deine Nachrichten an diesen Anbieter; die Weitergabe von Bibliotheksmetadaten erfordert eine gesonderte Zustimmung.',
    faq5Title: 'Welche Sprachen gibt es?', faq5: 'Project Seeker ist auf Englisch, Italienisch, Französisch und Deutsch verfügbar. Die Sprache wählst du in den App-Einstellungen.',
    closing: 'Du hast schon etwas gemacht, das es wert ist, wieder gehört zu werden.', footerSource: 'Quellcode', credits: 'Hinweise zu Drittanbietern', licenses: 'Lizenzen der Abhängigkeiten', trademark: 'FL Studio und Ableton Live sind Marken ihrer jeweiligen Inhaber. Keine Verbindung oder Unterstützung durch diese Unternehmen.'
  }
};

const english = Object.fromEntries([...document.querySelectorAll('[data-i18n]')].map(element => [element.dataset.i18n, element.textContent]));
english.copied = 'SHA-256 copied.';
english.copyFailed = 'Copy unavailable: select and copy the value manually.';
translations.en = english;
const selector = document.getElementById('language');
let activeLanguage = 'en';

function setLanguage(language) {
  activeLanguage = Object.hasOwn(translations, language) ? language : 'en';
  const dictionary = translations[activeLanguage];
  document.documentElement.lang = activeLanguage;
  selector.value = activeLanguage;
  document.querySelectorAll('[data-i18n]').forEach(element => {
    element.textContent = dictionary[element.dataset.i18n] ?? english[element.dataset.i18n];
  });
  document.getElementById('copy-status').textContent = '';
  updatePreviewAlt();
}

const views = {projects: 'projects-dark.png', map: 'map-dark.png', album: 'album-dark.png'};
let activeView = 'projects';

function updatePreviewAlt() {
  const viewKey = {projects: 'viewProjects', map: 'viewMap', album: 'viewAlbum'}[activeView];
  document.getElementById('preview').alt = `Project Seeker — ${translations[activeLanguage][viewKey]}`;
}

document.querySelectorAll('[data-view]').forEach(button => {
  button.addEventListener('click', () => {
    activeView = button.dataset.view;
    const path = `docs/screenshots/${views[activeView]}`;
    document.getElementById('preview').src = path;
    document.getElementById('preview-link').href = path;
    document.querySelectorAll('[data-view]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    updatePreviewAlt();
  });
});

selector.addEventListener('change', () => {
  setLanguage(selector.value);
  try { localStorage.setItem('project-seeker-site-language', activeLanguage); } catch {}
});

document.getElementById('copy-hash').addEventListener('click', async () => {
  const status = document.getElementById('copy-status');
  const value = document.getElementById('installer-hash');
  try {
    await navigator.clipboard.writeText(value.textContent);
    status.textContent = translations[activeLanguage].copied;
  } catch {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(value);
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent = translations[activeLanguage].copyFailed;
  }
});

let initialLanguage = 'en';
try { initialLanguage = localStorage.getItem('project-seeker-site-language') || 'en'; } catch {}
setLanguage(initialLanguage);

angular.module('deciframeApp').controller('AcordesController', function($http, $window, ngProgressFactory, $anchorScroll, $location, GENEROS, PALETA_ACORDES) {
  var vm = this;
  vm.acordes = PALETA_ACORDES;
  vm.meusAcordes = [];
  vm.isSearching = false;
  vm.showSearchResultsCount = false;
  vm.esfigeSpeech =  "";
  vm.musics = [];
  vm.generos = GENEROS;
  vm.meuGenero = "";
  vm.progressbar = ngProgressFactory.createInstance();

  vm.addAcorde = function(acorde) {
    if (vm.meusAcordes.indexOf(acorde) == -1) {
      vm.meusAcordes.push(acorde);
    } else {
      var index = vm.meusAcordes.indexOf(acorde);
      if (index > -1) vm.meusAcordes.splice(index, 1);
    }
    vm.pesquisarPorAcordes();
  }
  vm.temAcorde = function(acorde) {
    return (vm.meusAcordes.indexOf(acorde) > -1);
  }

  var createChordsString = function(chords) {
    var str = "";
    for (var i = 0; i < chords.length; i++) {
      str = str.concat(chords[i].acorde, ',');
    }
    return str.substring(0, str.length-1);
  }

  vm.pesquisarPorAcordes = function() {
    if (vm.meusAcordes.length) {
      vm.progressbar.start();
      vm.esfigeSpeech = "Procurando músicas com base nos acordes...";
      vm.isSearching = true;
      vm.musics = [];

      var apiUrl = "";
      var searchString = "similares?acordes=".concat(createChordsString(vm.meusAcordes));
      if (vm.meuGenero !== "" && vm.meuGenero !== null) {
        searchString += "&generos="+vm.meuGenero;
      }
      $http.get(apiUrl.concat(searchString))
        .success(function(data) {
          vm.progressbar.complete();
          vm.esfigeSpeech = "Encontrei essas músicas";
          vm.isSearching = false;
          vm.showSearchResultsCount = true;
          vm.musics = data;
        })
        .error(function(data) {
          vm.esfigeSpeech = "Ops! Algo errado.";
          vm.isSearching = false;
          vm.showSearchResultsCount = false;
        });
    } else {
      vm.musics = [];
      vm.esfigeSpeech = "";
      vm.isSearching = false;
      vm.showSearchResultsCount = false;
    }
  }

  vm.goToLirics = function(music) {
    $window.open(music.url);
  };

  vm.goToResults = function() {
    vm.showSearchResultsCount = false;
    $("body").animate({scrollTop: $("#results").offset().top}, "slow");
  };
});

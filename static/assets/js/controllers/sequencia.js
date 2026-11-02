angular.module('deciframeApp').controller('SequenciaController', function($http, $window, ngProgressFactory, $anchorScroll, $location, GENEROS) {
  var COR = '#2E1C74';
  var TAM_PAGINA = 100;

  var vm = this;
  vm.sequenciasFamosas = [];
  vm.minhaSequencia = {};
  vm.isSearching = false;
  vm.showSearchResultsCount = false;
  vm.esfigeSpeech =  "";
  vm.musics = [];
  vm.generos = GENEROS;
  vm.meuGenero = "";
  vm.progressbar = ngProgressFactory.createInstance();

  vm.pagina = 1;
  vm.temMais = false;
  vm.carregandoMais = false;

  vm.novaSequencia = { nome: '', acordes: '' };
  vm.criando = false;
  vm.erroCadastro = '';
  vm.avisoCadastro = '';

  var montarSequencia = function(registro) {
    var acordes = [];
    for (var i = 0; i < registro.acordes.length; i++) {
      acordes.push({ 'acorde': registro.acordes[i], 'cor': COR });
    }
    return {
      'id': registro.id,
      'nome': registro.nome,
      'rotulo': registro.nome || registro.acordes.join(' - '),
      'acordes': acordes
    };
  };

  vm.carregarSequencias = function() {
    $http.get('sequencias')
      .success(function(data) {
        vm.sequenciasFamosas = [];
        for (var i = 0; i < data.length; i++) {
          vm.sequenciasFamosas.push(montarSequencia(data[i]));
        }
      })
      .error(function() {
        vm.erroCadastro = 'Não foi possível carregar o catálogo de sequências.';
      });
  };

  vm.carregarSequencias();

  vm.temAcorde = function(acorde) {
    if (vm.minhaSequencia.acordes) {
      return (vm.minhaSequencia.acordes.indexOf(acorde) > -1);
    } else {
      return false;
    }
  }

  var criarBusca = function(pagina) {
    var searchString = "similares?sequencia_id=" + vm.minhaSequencia.id + "&pagina=" + pagina;
    if (vm.meuGenero !== "" && vm.meuGenero !== null) {
      searchString += "&generos=" + encodeURIComponent(vm.meuGenero);
    }
    return searchString;
  };

  vm.pesquisarPorSequencia = function(sequencia) {
    if (sequencia) {
      vm.minhaSequencia = sequencia;
    }
    if (vm.minhaSequencia.id === undefined) {
      return;
    }
    vm.progressbar.start();
    vm.esfigeSpeech = "Procurando músicas com base na sequencia...";
    vm.isSearching = true;
    vm.musics = [];
    vm.pagina = 1;
    vm.temMais = false;

    $http.get(criarBusca(1))
      .success(function(data) {
        vm.progressbar.complete();
        vm.esfigeSpeech = "Encontrei essas músicas";
        vm.isSearching = false;
        vm.showSearchResultsCount = data.length > 0;
        vm.musics = data;
        vm.temMais = data.length === TAM_PAGINA;
      })
      .error(function(data) {
        vm.esfigeSpeech = "Ops! Algo errado.";
        vm.isSearching = false;
        vm.showSearchResultsCount = false;
      });
  }

  vm.carregarMais = function() {
    if (vm.carregandoMais || !vm.temMais || vm.minhaSequencia.id === undefined) {
      return;
    }
    vm.carregandoMais = true;
    var proxima = vm.pagina + 1;

    $http.get(criarBusca(proxima))
      .success(function(data) {
        vm.musics = vm.musics.concat(data);
        vm.pagina = proxima;
        vm.temMais = data.length === TAM_PAGINA;
        vm.carregandoMais = false;
      })
      .error(function() {
        vm.carregandoMais = false;
      });
  }

  vm.criar = function() {
    if (!vm.novaSequencia.acordes.replace(/,/g, ' ').trim()) {
      vm.erroCadastro = 'Informe pelo menos um acorde.';
      return;
    }

    vm.criando = true;
    vm.erroCadastro = '';
    vm.avisoCadastro = '';

    var corpo = {
      nome: vm.novaSequencia.nome,
      acordes: vm.novaSequencia.acordes
    };

    $http.post('sequencias', corpo)
      .success(function(registro, status) {
        vm.criando = false;
        var sequencia = montarSequencia(registro);

        var existe = false;
        for (var i = 0; i < vm.sequenciasFamosas.length; i++) {
          if (vm.sequenciasFamosas[i].id === sequencia.id) {
            existe = true;
            break;
          }
        }
        if (!existe) {
          vm.sequenciasFamosas.push(sequencia);
        }

        vm.novaSequencia = { nome: '', acordes: '' };
        vm.avisoCadastro = (status === 200)
          ? 'Essa sequência já existia; usei a existente.'
          : 'Sequência cadastrada. ' + registro.total_musicas + ' música(s) encontrada(s).';

        vm.pesquisarPorSequencia(sequencia);
      })
      .error(function(data) {
        vm.criando = false;
        vm.erroCadastro = (data && data.erro)
          ? data.erro
          : 'Não foi possível cadastrar a sequência.';
      });
  }

  vm.limparPesquisa = function() {
    vm.minhaSequencia = {};
    vm.musics = [];
    vm.pagina = 1;
    vm.temMais = false;
    vm.showSearchResultsCount = false;
  }

  vm.goToLirics = function(music) {
    $window.open(music.url);
  };

  vm.goToResults = function() {
    vm.showSearchResultsCount = false;
    $("body").animate({scrollTop: $("#results").offset().top}, "slow");
  };
});

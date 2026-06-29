
const golpes = [
  {
    id: 1,
    nome: "Golpe do Marketplace",
    categoria: "Compras Online",
    risco: "alto",
    descricao: "Venda de produtos falsos, anúncios enganosos e pagamentos fora da plataforma.",
    sinais: ["Preço muito abaixo do mercado", "Vendedor pede pagamento por fora", "Produto nunca chega"],
    comoEvitar: "Sempre pague dentro da plataforma e desconfie de preços muito baixos."
  },
  {
    id: 2,
    nome: "Golpe de Investimento",
    categoria: "Financeiro",
    risco: "alto",
    descricao: "Pirâmides financeiras, promessas de lucro garantido e falsos especialistas.",
    sinais: ["Promete ganhos acima de 10% ao mês", "Pressão para investir rápido", "Indicação de amigos para ganhar mais"],
    comoEvitar: "Verifique se a corretora tem registro na CVM. Nenhum investimento garante lucro."
  },
  {
    id: 3,
    nome: "Phishing",
    categoria: "Email / SMS",
    risco: "alto",
    descricao: "Links falsos enviados por e-mail ou SMS para roubar dados pessoais e bancários.",
    sinais: ["Link com URL estranha", "Urgência para clicar", "E-mail com erros de português"],
    comoEvitar: "Nunca clique em links suspeitos. Acesse o site digitando o endereço direto."
  },
  {
    id: 4,
    nome: "Golpe do PIX",
    categoria: "Pagamentos",
    risco: "alto",
    descricao: "Fraudes envolvendo transferências via PIX, como chave aleatória falsa ou comprovantes adulterados.",
    sinais: ["Comprovante enviado antes de você receber", "Pedido de devolução de valor", "Chave PIX não pertence a quem diz ser"],
    comoEvitar: "Confirme o nome do destinatário antes de enviar qualquer valor."
  },
  {
    id: 5,
    nome: "WhatsApp Clonado",
    categoria: "Redes Sociais",
    risco: "médio",
    descricao: "O golpista assume sua conta do WhatsApp e pede dinheiro aos seus contatos.",
    sinais: ["Alguém que você conhece pedindo dinheiro via WhatsApp", "Pedido de código SMS", "Conta desconhecida"],
    comoEvitar: "Ative a verificação em duas etapas no WhatsApp. Nunca compartilhe seu código."
  },
  {
    id: 6,
    nome: "Boleto Falso",
    categoria: "Pagamentos",
    risco: "médio",
    descricao: "Boletos com dados bancários trocados enviados por e-mail ou correspondência.",
    sinais: ["Boleto recebido sem solicitação", "Dados do beneficiário diferentes", "Link para download de boleto"],
    comoEvitar: "Sempre gere o boleto diretamente no site da empresa. Verifique o beneficiário."
  }
];

// ---------- 2. PERGUNTAS DO SIMULADOR ----------
const perguntasSimulador = [
  {
    id: 1,
    situacao: "Você recebeu uma mensagem no WhatsApp de um número desconhecido dizendo que é seu amigo e pedindo R$300 emprestado via PIX urgentemente.",
    eGolpe: true,
    explicacao: "Este é um golpe clássico de WhatsApp clonado. O golpista finge ser alguém de confiança para conseguir dinheiro rapidamente. Sempre ligue para a pessoa antes de transferir qualquer valor."
  },
  {
    id: 2,
    situacao: "Uma corretora oferece rendimento garantido de 25% ao mês em um investimento exclusivo e pede que você indique amigos para ganhar bônus.",
    eGolpe: true,
    explicacao: "Rendimentos garantidos acima de 1% ao mês já são suspeitos. 25% ao mês é uma pirâmide financeira. A indicação de amigos para bônus é característica de esquemas fraudulentos."
  },
  {
    id: 3,
    situacao: "Você vai fazer uma compra online e o site pede o código de verificação do cartão (CVV) para finalizar o pedido.",
    eGolpe: false,
    explicacao: "Isso é normal e seguro em sites legítimos. O CVV é uma camada de segurança padrão em compras online. Certifique-se apenas de que o site tem HTTPS e é confiável."
  },
  {
    id: 4,
    situacao: "Você recebeu um SMS do seu banco dizendo que sua conta será bloqueada. O SMS pede que você clique em um link para regularizar.",
    eGolpe: true,
    explicacao: "Bancos nunca enviam links por SMS pedindo dados. Este é um ataque de phishing. Em caso de dúvida, ligue para o número oficial do banco impresso no cartão."
  },
  {
    id: 5,
    situacao: "Um vendedor no marketplace aceita apenas pagamento por transferência direta, pois diz que a plataforma cobra taxa alta.",
    eGolpe: true,
    explicacao: "Pagamentos fora da plataforma eliminam qualquer proteção ao comprador. É um dos golpes mais comuns no Marketplace. Sempre pague dentro da plataforma."
  }
];

// ---------- 3. NAVBAR: SCROLL + HAMBÚRGUER ----------
(function initNavbar() {
  const navbar    = document.getElementById("navbar");
  const hamburger = document.getElementById("hamburger");
  const navMenu   = document.getElementById("navMenu");

  if (!navbar) return;

  // Scroll: adiciona classe "scrolled"
  window.addEventListener("scroll", () => {
    navbar.classList.toggle("scrolled", window.scrollY > 20);
  });

  // Hambúrguer: abre/fecha menu mobile
  if (hamburger && navMenu) {
    hamburger.addEventListener("click", () => {
      const isOpen = navMenu.classList.toggle("open");
      hamburger.classList.toggle("open", isOpen);
      hamburger.setAttribute("aria-expanded", isOpen);
    });

    // Fecha ao clicar em um link
    navMenu.querySelectorAll(".navbar__link").forEach(link => {
      link.addEventListener("click", () => {
        navMenu.classList.remove("open");
        hamburger.classList.remove("open");
        hamburger.setAttribute("aria-expanded", false);
      });
    });
  }

  // Marca o link ativo conforme a página atual
  const currentPage = window.location.pathname.split("/").pop() || "index.html";
  navMenu && navMenu.querySelectorAll(".navbar__link").forEach(link => {
    const href = link.getAttribute("href");
    if (href === currentPage) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });
})();

// ---------- 4. ANIMAÇÕES FADE-IN (Intersection Observer) ----------
(function initFadeIn() {
  const elements = document.querySelectorAll(".fade-in");
  if (!elements.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  elements.forEach(el => observer.observe(el));
})();

// ---------- 5. PESQUISA DE GOLPES ----------
/**
 * Filtra o array de golpes com base em um termo de pesquisa.
 * @param {string} termo - Texto digitado pelo usuário.
 * @returns {Array} Lista de golpes que correspondem ao termo.
 */
function pesquisarGolpes(termo) {
  const termoBaixo = termo.toLowerCase().trim();
  if (!termoBaixo) return golpes;

  return golpes.filter(golpe =>
    golpe.nome.toLowerCase().includes(termoBaixo) ||
    golpe.categoria.toLowerCase().includes(termoBaixo) ||
    golpe.descricao.toLowerCase().includes(termoBaixo)
  );
}

// Inicializa pesquisa se o campo existir na página
(function initPesquisa() {
  const input = document.getElementById("campoPesquisa");
  const lista = document.getElementById("listaGolpes");
  if (!input || !lista) return;

  renderizarGolpes(golpes, lista);

  input.addEventListener("keyup", () => {
    const resultados = pesquisarGolpes(input.value);
    renderizarGolpes(resultados, lista);
  });
})();

// ---------- 6. RENDERIZAR CARDS DE GOLPES ----------
/**
 * Gera e insere os cards de golpes no container.
 * @param {Array} lista  - Array de golpes a exibir.
 * @param {HTMLElement} container - Elemento onde os cards serão inseridos.
 */
function renderizarGolpes(lista, container) {
  if (!container) return;

  if (lista.length === 0) {
    container.innerHTML = `
      <div class="sem-resultados">
        <p>Nenhum golpe encontrado. Tente outro termo.</p>
      </div>`;
    return;
  }

  container.innerHTML = lista.map(golpe => `
    <article class="card-golpe fade-in" data-id="${golpe.id}">
      <div class="card-golpe__header">
        <span class="card-golpe__categoria">${golpe.categoria}</span>
        <span class="card-golpe__risco card-golpe__risco--${golpe.risco}">${golpe.risco}</span>
      </div>
      <h3 class="card-golpe__nome">${golpe.nome}</h3>
      <p class="card-golpe__desc">${golpe.descricao}</p>
      <button class="btn btn--primary card-golpe__btn" onclick="verDetalhes(${golpe.id})">
        Saiba Mais →
      </button>
    </article>
  `).join("");

  // Reativa animações nos novos cards
  container.querySelectorAll(".fade-in").forEach((el, i) => {
    setTimeout(() => el.classList.add("visible"), i * 80);
  });
}

// ---------- 7. DETALHE DO GOLPE ----------
/**
 * Exibe informações detalhadas de um golpe específico.
 * @param {number} id - ID do golpe.
 */
function verDetalhes(id) {
  const golpe = golpes.find(g => g.id === id);
  if (!golpe) return;

  // Exemplo simples: alert educativo (substituir por modal na versão final)
  const sinais = golpe.sinais.map(s => `• ${s}`).join("\n");
  alert(
    `🛡️ ${golpe.nome}\n\n` +
    `${golpe.descricao}\n\n` +
    `⚠️ Sinais de alerta:\n${sinais}\n\n` +
    `✅ Como evitar:\n${golpe.comoEvitar}`
  );
}

// ---------- 8. SIMULADOR ----------
let simuladorIndex  = 0;
let simuladorPontos = 0;

/**
 * Inicializa o simulador na página simulador.html.
 */
function initSimulador() {
  const container = document.getElementById("simulador");
  if (!container) return;

  simuladorIndex  = 0;
  simuladorPontos = 0;
  exibirPergunta(container);
}

function exibirPergunta(container) {
  if (simuladorIndex >= perguntasSimulador.length) {
    exibirResultadoFinal(container);
    return;
  }

  const pergunta = perguntasSimulador[simuladorIndex];
  container.innerHTML = `
    <div class="simulador__progresso">
      Pergunta ${simuladorIndex + 1} de ${perguntasSimulador.length}
    </div>
    <p class="simulador__situacao">${pergunta.situacao}</p>
    <div class="simulador__acoes">
      <button class="btn btn--danger" onclick="responderSimulador(true)">⚠️ É Golpe</button>
      <button class="btn btn--success" onclick="responderSimulador(false)">✅ É Seguro</button>
    </div>
  `;
}

/**
 * Processa a resposta do usuário no simulador.
 * @param {boolean} respostaUsuario - true se o usuário marcou "É Golpe".
 */
function responderSimulador(respostaUsuario) {
  const pergunta  = perguntasSimulador[simuladorIndex];
  const acertou   = respostaUsuario === pergunta.eGolpe;
  if (acertou) simuladorPontos++;

  const container = document.getElementById("simulador");
  container.innerHTML = `
    <div class="simulador__feedback simulador__feedback--${acertou ? "acerto" : "erro"}">
      <strong>${acertou ? "✅ Correto!" : "❌ Errado!"}</strong>
      <p>${pergunta.explicacao}</p>
      <button class="btn btn--primary" onclick="proximaPergunta()">
        ${simuladorIndex + 1 < perguntasSimulador.length ? "Próxima →" : "Ver Resultado"}
      </button>
    </div>
  `;
}

function proximaPergunta() {
  simuladorIndex++;
  const container = document.getElementById("simulador");
  exibirPergunta(container);
}

function exibirResultadoFinal(container) {
  const total      = perguntasSimulador.length;
  const porcentagem = Math.round((simuladorPontos / total) * 100);

  let mensagem = "";
  if (porcentagem === 100) mensagem = "🏆 Perfeito! Você está bem protegido.";
  else if (porcentagem >= 60) mensagem = "👍 Bom resultado! Mas vale revisar os erros.";
  else mensagem = "⚠️ Atenção! Você pode ser vulnerável a golpes. Explore os tipos de golpes.";

  container.innerHTML = `
    <div class="simulador__resultado">
      <h2>Resultado Final</h2>
      <div class="simulador__pontos">${simuladorPontos}/${total}</div>
      <p>${mensagem}</p>
      <div class="simulador__acoes">
        <button class="btn btn--primary" onclick="initSimulador()">Tentar Novamente</button>
        <a href="golpes.html" class="btn btn--ghost">Ver Todos os Golpes</a>
      </div>
    </div>
  `;
}

// ---------- 9. INICIALIZAÇÃO GERAL ----------
document.addEventListener("DOMContentLoaded", () => {
  initSimulador();
});

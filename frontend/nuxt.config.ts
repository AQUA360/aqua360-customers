export default defineNuxtConfig({

  devtools: {
    enabled: true,
    // VS Code Server options
    vscode: {}
  },

  runtimeConfig: {
    apiSecret: process.env.NUXT_API_SECRET, // can be overridden by NUXT_API_SECRET environment variable

    public: {
      externalGot: process.env.NUXT_EXTERNAL_GOT, // can be overridden by NUXT_EXTERNAL_GOT environment variable
      apiHost: process.env.NUXT_PUBLIC_API_HOST, // can be overridden by NUXT_PUBLIC_API_HOST environment variable
      defaultLocale: process.env.LANGUAGE, // default locale for i18n
      env: process.env.ENV, // environment name (prod, dev, test, etc.)
      verifactuEnabled: process.env.VERIFACTU_ENABLED === 'True', // Verifactu feature flag
      // Installations of the same customer that live on their own URL (one database each), listed in
      // the exploitation selector so the user can jump to them. JSON array of {name, url}, can be
      // overridden by NUXT_PUBLIC_EXPLOITATION_SITES environment variable. Empty = single installation.
      exploitationSites: process.env.NUXT_PUBLIC_EXPLOITATION_SITES,
    }
  },

  modules: ['@nuxtjs/i18n', "@nuxtjs/tailwindcss", "@vesp/nuxt-fontawesome", '@pinia/nuxt', "@nuxt/icon"],


  ssr: false,

  icon: {
    serverBundle: {
      collections: ['fa6-solid', 'fa6-regular', 'healthicons', 'mdi', 'my-icon']
    },
    // Default 256KB limit breaks build: client bundle ~459KB with ssr:false + bundled collections.
    clientBundle: {
      sizeLimitKb: 640,
    },
    customCollections: [
      {
        prefix: 'my-icon',
        dir: 'public',
      },
    ]
  },

  alias: {
    pinia: "pinia",
  },


  plugins: [
    '~/plugins/npm/vue-select.js',
    '~/plugins/npm/toast.js',
    '~/plugins/npm/vue-datepicker.js',

    '~/plugins/global-error-handler.client.js',

    '~/plugins/directives/no-dash.js',
    '~/plugins/directives/validate-email.js',
    '~/plugins/directives/format-route-code.js',
    '~/plugins/directives/numeric-only.js',
    '~/plugins/directives/click-outside.js',
    '~/plugins/helpers/AddressHelper.js',

    '~/plugins/api/api-manager.js',
    '~/plugins/api/api.js',

    '~/plugins/api/logger/logger-api.js',
    '~/plugins/api/logger/logger-change-api.js',
    '~/plugins/api/logger/ov-logs-api.js',

    '~/plugins/api/observations/observation-api.js',

    //catastro
    '~/plugins/api/catastro/catastro-api.js',

    // coredata
    '~/plugins/api/coredata/config-project-api.js',
    '~/plugins/api/coredata/address-api.js',
    '~/plugins/api/coredata/person-api.js',
    '~/plugins/api/coredata/person-address-api.js',
    '~/plugins/api/coredata/person-bank-api.js',
    '~/plugins/api/coredata/person-contact-api.js',
    '~/plugins/api/coredata/street-api.js',
    '~/plugins/api/coredata/cnae-api.js',
    '~/plugins/api/coredata/person-bank-sepa-documentation-api.js',
    '~/plugins/api/coredata/call-register-api.js',
    '~/plugins/api/coredata/person-piggy-bank-api.js',

    // service
    '~/plugins/api/service/configlist-api.js',
    '~/plugins/api/service/exploitation-api.js',
    '~/plugins/api/service/connection-api.js',
    '~/plugins/api/service/connection-request-api.js',
    '~/plugins/api/service/cluster-api.js',
    '~/plugins/api/service/cluster-nozzle-api.js',
    '~/plugins/api/service/meter-api.js',
    '~/plugins/api/service/meter-manufacturer-api.js',
    '~/plugins/api/service/meter-model-api.js',
    '~/plugins/api/service/supply-point-api.js',
    '~/plugins/api/service/supply-point-request-api.js',
    '~/plugins/api/service/route-api.js',
    '~/plugins/api/service/property-api.js',
    '~/plugins/api/service/dma-api.js',
    '~/plugins/api/service/tank-api.js',
    '~/plugins/api/service/status-api.js',
    '~/plugins/api/service/supply-cut-api.js',

    // contract
    '~/plugins/api/contract/bonification-type-api.js',
    '~/plugins/api/contract/bonification-api.js',
    '~/plugins/api/contract/bonification-documentation-api.js',
    '~/plugins/api/contract/bail-type-api.js',
    '~/plugins/api/contract/bail-api.js',
    '~/plugins/api/contract/piggy-bank-api.js',
    '~/plugins/api/contract/contract-api.js',
    '~/plugins/api/contract/contract-use-aca-api.js',
    '~/plugins/api/contract/contract-request-api.js',
    '~/plugins/api/contract/contract-request-type-api.js',
    '~/plugins/api/contract/contract-payment-api.js',
    '~/plugins/api/contract/contract-request-documentation-api.js',
    '~/plugins/api/contract/variable-api.js',
    '~/plugins/api/contract/variable-type-api.js',
    '~/plugins/api/contract/contract-surrogation-api.js',
    '~/plugins/api/contract/contract-termination-api.js',
    '~/plugins/api/contract/clause-template-api.js',
    '~/plugins/api/contract/contract-clauses-api.js',
    '~/plugins/api/contract/aca-document-api.js',
    '~/plugins/api/contract/aca-bonification-api.js',
    '~/plugins/api/contract/general-invoice-api.js',

    // order
    '~/plugins/api/order/order-type-api.js',
    '~/plugins/api/order/order-api.js',
    '~/plugins/api/order/operator-api.js',
    '~/plugins/api/order/order-reason-api.js',
    '~/plugins/api/order/order-priority-api.js',

    // pricing
    '~/plugins/api/pricing/accounting-pricing-api.js',
    '~/plugins/api/pricing/accounting-concept-api.js',
    '~/plugins/api/pricing/accounting-type-api.js',
    '~/plugins/api/pricing/accounting-cost-center-api.js',
    '~/plugins/api/pricing/billing-range-api.js',
    '~/plugins/api/pricing/line-item-type-api.js',
    '~/plugins/api/pricing/line-item-api.js',
    '~/plugins/api/pricing/price-rate-api.js',
    '~/plugins/api/pricing/price-interval-stretch-api.js',
    '~/plugins/api/pricing/price-interval-api.js',
    '~/plugins/api/pricing/publication-api.js',
    '~/plugins/api/pricing/product-api.js',
    '~/plugins/api/pricing/tax-api.js',
    '~/plugins/api/pricing/adjustment-api.js',
    '~/plugins/api/pricing/article-code-api.js',
    '~/plugins/api/pricing/adjustment-condition-api.js',
    '~/plugins/api/pricing/adjustment-interval-stretch-api.js',
    '~/plugins/api/pricing/price-variable-interval-api.js',
    '~/plugins/api/pricing/price-variable-interval-stretch-api.js',

    // billing
    '~/plugins/api/billing/billing-api.js',
    '~/plugins/api/billing/reading-api.js',
    '~/plugins/api/billing/reading-batch-api.js',
    '~/plugins/api/billing/reading-batch-template-api.js',
    '~/plugins/api/billing/contract-estimation-api.js',
    '~/plugins/api/billing/billing-batch-api.js',
    '~/plugins/api/billing/billing-batch-template-api.js',
    '~/plugins/api/billing/invoice-api.js',
    '~/plugins/api/billing/invoice-template-api.js',
    '~/plugins/api/billing/payment-api.js',
    '~/plugins/api/billing/message-api.js',
    '~/plugins/api/billing/biller-api.js',
    '~/plugins/api/billing/general-payment-api.js',
    '~/plugins/api/billing/claim-request-api.js',
    '~/plugins/api/billing/estimated-bag-api.js',
    '~/plugins/api/billing/commitment-deposit-api.js',
    '~/plugins/api/billing/payment-commitment-api.js',
    '~/plugins/api/billing/vulnerability-request-api.js',
    '~/plugins/api/billing/vulnerability-request-type-api.js',
    '~/plugins/api/billing/reading-document-api.js',
    '~/plugins/api/billing/smart-metering-api.js',
    '~/plugins/api/billing/sepa-remittance-api.js',
    '~/plugins/api/billing/sepa-remittance-return-api.js',
    '~/plugins/api/billing/joined-payment-api.js',
    '~/plugins/api/billing/config-aca-api.js',
    '~/plugins/api/billing/invoice-sequence-api.js',

    //verifactu
    '~/plugins/api/billing/verifactu-api.js',

    //statistics
    '~/plugins/api/statistics/reports-api.js',
    '~/plugins/api/statistics/billing-consumption-api.js',
    '~/plugins/api/statistics/statistics-contracts-api.js',
    '~/plugins/api/statistics/general-statistics-api.js',
    '~/plugins/api/statistics/daily-activity-api.js',
    '~/plugins/api/statistics/reading-batch-export-column-api.js',
    '~/plugins/api/statistics/reading-batch-import-template-api.js',
    '~/plugins/api/statistics/reading-batch-import-column-api.js',
    '~/plugins/api/statistics/daily-document-api.js',
    '~/plugins/api/statistics/daily-document-template-api.js',

    //search
    '~/plugins/api/search/search-api.js',

    //document manager
    '~/plugins/api/documentmanager/document-manager-api.js',
    '~/plugins/api/documentmanager/document-sign-api.js',
    '~/plugins/api/documentmanager/export-job-api.js',

    //notification
    '~/plugins/api/notification/notification-api.js',
    '~/plugins/api/notification/calendar-task-api.js',
    '~/plugins/api/notification/incident-api.js',
    '~/plugins/api/notification/incident-report-api.js',
    '~/plugins/api/notification/general-note-api.js',

    //fraud
    '~/plugins/api/fraud/fraud-api.js',
    '~/plugins/api/fraud/fraud-report-api.js',
    '~/plugins/api/fraud/consumption-management-api.js',

    //communication
    '~/plugins/api/communication/communication-api.js',
    '~/plugins/api/communication/communication-process-api.js',
    '~/plugins/api/communication/message-template-api.js',

    //auth
    '~/plugins/api/auth/group-api.js',
    '~/plugins/api/auth/user-api.js',

    //got - operator platform
    '~/plugins/api/got/got-api.js',

    //i18n
    '~/plugins/i18n-init.client.js',
  ],

  i18n: {
    // El mòdul l'activa per defecte i ell mateix recomana desactivar-lo: causa
    // problemes i queda obsolet a la v10. A més dispara molt la memòria del build.
    bundle: {
      optimizeTranslationDirective: false,
    },
    locales: ['ca', 'es', 'gl', 'en'], // used in URL path prefix
    defaultLocale: process.env.LANGUAGE,// default locale of your project for Nuxt pages and routings
    strategy: 'no_prefix',
    // `lazy` ja no existeix a la v10 del mòdul: la càrrega mandrosa és obligatòria.
    detectBrowserLanguage: false, // Disable automatic browser language detection
  },

  app: {
    head: {
      htmlAttrs: {
        lang: process.env.LANGUAGE || 'ca'
      },
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,300..800;1,300..800&display=swap' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200' },
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' },
        { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32x32.png' },
        { rel: 'icon', type: 'image/png', sizes: '16x16', href: '/favicon-16x16.png' }
      ],
    }
  },

  fontawesome: {
    icons: {
      solid: ['street-view', 'industry', 'person-walking-arrow-right', 'people-arrows', 'shuffle', 'address-book', 'credit-card', 'users', 'file-circle-plus', 'file-signature', 'file-contract', 'tree-city', 'microchip', 'magnifying-glass', 'star', 'comment', 'list', 'gear', 'arrow-right-from-bracket', 'bell', 'envelope', 'floppy-disk', 'bars', 'gauge', 'map', 'home', 'pencil', 'pen-to-square', 'trash', 'trash-can', 'angles-right', 'ellipsis-vertical', 'plus', 'square-plus', 'circle-plus', 'eye', 'bullseye', 'rotate-right', 'book', 'book-open', 'note-sticky', 'gauge', 'address-card', 'droplet-slash', 'file-pdf', 'circle-nodes', 'sort', 'sort-up', 'sort-down', 'angle-right', 'angle-left', 'file', 'file-alt', 'plug', 'plug-circle-plus', 'circle', 'circle-check', 'file-circle-xmark', 'circle-xmark', 'check', 'xmark', 'asterisk', 'spinner', 'search', 'house-chimney', 'scissors', 'chevron-right', 'chevron-left', 'screwdriver-wrench', 'helmet-safety', 'hand-pointer'],
      regular: ['comment', 'address-card', 'star', 'floppy-disk', 'map', 'pen-to-square', 'trash-can', 'square-plus', 'eye', 'note-sticky', 'address-card', 'calendar', 'file-pdf', 'file', 'file-alt', 'circle', 'circle-check', 'circle-xmark', 'hand-pointer'],
      brands: [],
    }
  },

  vue: {
    compilerOptions: {
      isCustomElement: (tag) => tag.startsWith('relative-time')
    }
  },

  css: [
    '~/assets/styles/global.css'
  ],

  build: { transpile: ['vue-toastification'] },
  compatibilityDate: '2025-01-13'
})
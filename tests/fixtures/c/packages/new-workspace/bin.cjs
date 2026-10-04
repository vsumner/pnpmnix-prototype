#!/usr/bin/env node
console.log(JSON.stringify({value:require("./index.cjs").value,zone:process.env.MAINTENANCE_ZONE}));

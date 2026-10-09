<script setup>
defineProps({
    height: {
        type: Number,
        default: 1
    },
    has_icon: {
        type: Boolean,
        default: true,
    },
    is_calendar: {
        type: Boolean,
        default: false,
    }
})
</script>

<template>
    <div class="container">
        <div class="row">
            <div v-for="i in height" :key="i" class="col-12 col-md-4 pt-5">
                <div v-if="!is_calendar" class="placeholder wave">
                    <div v-if="has_icon" class="square"><br></div>
                    <div class="line"><br></div>
                    <div class="line"><br></div>
                </div>
                <div v-else class="placeholder wave calendar-grid">
                    <div v-for="j in 7" :key="'day-' + j" class="calendar-item">
                        <br />
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped lang="css">
.placeholder {
    padding: 0 10px;
    border-radius: 5px;

    &.pulse div {
        animation: pulse 1s infinite ease-in-out;
        -webkit-animation: pulse 1s infinite ease-in-out;
    }

    &.wave div {
        animation: wave 1s infinite linear forwards;
        -webkit-animation: wave 1s infinite linear forwards;
        background: #f6f7f8;
        background: linear-gradient(to right, #eeeeee 8%, #dddddd 18%, #eeeeee 33%);
        background-size: 800px 104px;
    }

    div {
        background: #E8E8E8;
    }

    .square {
        float: left;
        width: 20px;
        height: 20px;
        margin: 0 10px 5px 0;
    }


    .line {
        height: 10px;
        margin: 0 0 5px 30px;
        width: 90%;
    }

    .circle {
        float: left;
        width: 50px;
        height: 50px;
        margin: 0 15px 10px 0;
        border-radius: 50%;
    }


}

.calendar-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 10px;
}

.calendar-item {
    width: 77px;
    height: 30px;
    border-radius: 10px;
}

@keyframes pulse {
    0% {
        background-color: rgba(165, 165, 165, .1);
    }

    50% {
        background-color: rgba(165, 165, 165, .3);
    }

    100% {
        background-color: rgba(165, 165, 165, .1);
    }
}

@-webkit-keyframes pulse {
    0% {
        background-color: rgba(165, 165, 165, .1);
    }

    50% {
        background-color: rgba(165, 165, 165, .3);
    }

    100% {
        background-color: rgba(165, 165, 165, .1);
    }
}

@keyframes wave {
    0% {
        background-position: -468px 0
    }

    100% {
        background-position: 468px 0
    }
}

@-webkit-keyframes wave {
    0% {
        background-position: -468px 0
    }

    100% {
        background-position: 468px 0
    }
}
</style>
